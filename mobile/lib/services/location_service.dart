import 'dart:async';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:geolocator/geolocator.dart';

import 'api.dart';
import 'offline_queue.dart';

class LocationShareService {
  StreamSubscription<Position>? _sub;
  Timer? _retry;
  int _generation = 0;
  String? lastError;
  void Function(String)? onError;
  Future<void> stopLocal() async {
    _generation++;
    _retry?.cancel();
    await _sub?.cancel();
    _sub = null;
    await _queue.clear();
  }

  final _battery = Battery();
  final _queue = OfflineLocationQueue();
  bool get running => _sub != null;

  Future<LocationPermission> ensurePermission({
    bool requestBackground = false,
  }) async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw Exception('Ative a localização do aparelho.');
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw Exception('Permissão de localização não concedida.');
    }

    if (requestBackground && permission == LocationPermission.whileInUse) {
      // Android/iOS decidem se e quando a autorização "Sempre" pode ser apresentada.
      // Uma negativa é respeitada e nunca é contornada.
      try {
        permission = await Geolocator.requestPermission();
      } catch (_) {}
    }
    return permission;
  }

  LocationSettings _settings(String mode) {
    final distance = switch (mode) {
      'economy' => 500,
      'high' => 50,
      _ => 150,
    };
    final accuracy = mode == 'economy'
        ? LocationAccuracy.medium
        : LocationAccuracy.high;

    if (Platform.isAndroid) {
      return AndroidSettings(
        accuracy: accuracy,
        distanceFilter: distance,
        intervalDuration: Duration(
          seconds: mode == 'high'
              ? 20
              : mode == 'economy'
              ? 120
              : 60,
        ),
        foregroundNotificationConfig: const ForegroundNotificationConfig(
          notificationTitle: 'JR Family — localização ativa',
          notificationText:
              'Compartilhando sua localização com responsáveis autorizados.',
          enableWakeLock: true,
          setOngoing: true,
        ),
      );
    }
    if (Platform.isIOS) {
      return AppleSettings(
        accuracy: accuracy,
        activityType: ActivityType.otherNavigation,
        distanceFilter: distance,
        pauseLocationUpdatesAutomatically: true,
        showBackgroundLocationIndicator: true,
        allowBackgroundLocationUpdates: true,
      );
    }
    return LocationSettings(accuracy: accuracy, distanceFilter: distance);
  }

  Future<void> start({
    required String familyId,
    required String deviceId,
    required String memberId,
    String mode = 'balanced',
  }) async {
    if (Platform.isAndroid) {
      await const MethodChannel('com.jrfamily.app/permissions')
          .invokeMethod<bool>('notifications');
    }
    final permission = await ensurePermission(requestBackground: true);
    final backgroundAuthorized = permission == LocationPermission.always;
    await Api.I.dio.patch(
      '/families/$familyId/devices/$deviceId/permissions',
      data: {
        'location': 'authorized',
        'background': backgroundAuthorized ? 'authorized' : 'limited',
        'sharing_enabled': true,
      },
    );

    await _sub?.cancel();
    final generation = ++_generation;
    lastError = null;
    _retry?.cancel();
    _retry = Timer.periodic(const Duration(seconds: 60), (_) async {
      try {
        await _queue.flush();
      } catch (_) {
        /* retry while running */
      }
    });
    await _queue.flush();
    _sub = Geolocator.getPositionStream(locationSettings: _settings(mode))
        .listen(
          (position) async {
            int? battery;
            try {
              battery = await _battery.batteryLevel;
            } catch (_) {}
            if (generation != _generation) return;
            final payload = <String, dynamic>{
              'latitude': position.latitude,
              'longitude': position.longitude,
              'accuracy_m': position.accuracy,
              'speed_mps': position.speed < 0 ? null : position.speed,
              'battery_percent': battery,
              'source_mode': mode,
              'captured_at': position.timestamp.toUtc().toIso8601String(),
            };
            try {
              await _queue.enqueue(deviceId, payload);
              if (generation != _generation) {
                await _queue.clear();
                return;
              }
              await _queue.flush();
            } catch (error) {
              lastError = 'Sincronização pendente: $error';
            }
          },
          onError: (Object error) {
            lastError = 'Localização indisponível. Verifique GPS e permissões.';
            onError?.call(lastError!);
            stopLocal();
          },
        );
  }

  Future<void> stop({
    required String familyId,
    required String deviceId,
  }) async {
    await stopLocal();
    await Api.I.dio.patch(
      '/families/$familyId/devices/$deviceId/permissions',
      data: {
        'location': 'authorized',
        'background': 'off',
        'sharing_enabled': false,
      },
    );
  }

  Future<Position?> currentOrNull() async {
    try {
      await ensurePermission();
      return await Geolocator.getCurrentPosition();
    } catch (_) {
      return null;
    }
  }
}
