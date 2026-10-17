import 'dart:async';
import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'push_service.dart';

class DeviceService {
  DeviceService._();
  static final DeviceService I = DeviceService._();

  StreamSubscription<String>? _pushSub;
  String _key(String familyId, String memberId) =>
      'jr_device_${familyId}_$memberId';

  Future<Map<String, String>> _metadata() async {
    final package = await PackageInfo.fromPlatform();
    final info = DeviceInfoPlugin();
    if (Platform.isAndroid) {
      final a = await info.androidInfo;
      return {
        'platform': 'android',
        'device_name': '${a.manufacturer} ${a.model}'.trim(),
        'os_version': 'Android ${a.version.release} (SDK ${a.version.sdkInt})',
        'app_version': '${package.version}+${package.buildNumber}',
      };
    }
    if (Platform.isIOS) {
      final i = await info.iosInfo;
      return {
        'platform': 'ios',
        'device_name': i.name.isEmpty ? i.model : i.name,
        'os_version': '${i.systemName} ${i.systemVersion}',
        'app_version': '${package.version}+${package.buildNumber}',
      };
    }
    return {
      'platform': Platform.operatingSystem,
      'device_name': 'JR Family',
      'os_version': Platform.operatingSystemVersion,
      'app_version': '${package.version}+${package.buildNumber}',
    };
  }

  Future<void> _listenForPushChanges(String deviceId) async {
    await _pushSub?.cancel();
    _pushSub = PushService.I.tokenChanges.listen((token) async {
      try {
        await Api.I.dio.patch(
          '/devices/$deviceId/push-token',
          data: {'push_token': token},
        );
      } catch (_) {}
    });
  }

  Future<String> ensureDevice({
    required String familyId,
    required String memberId,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final key = _key(familyId, memberId);
    final existing = prefs.getString(key);
    final meta = await _metadata();
    final pushToken = await PushService.I.requestPermissionAndToken();
    if (existing != null) {
      await Api.I.dio.patch(
        '/devices/$existing/push-token',
        data: {
          'push_token': pushToken,
          'app_version': meta['app_version'],
          'os_version': meta['os_version'],
        },
      );
      await _listenForPushChanges(existing);
      return existing;
    }

    final response = await Api.I.dio.post(
      '/families/$familyId/devices',
      data: {'member_id': memberId, ...meta, 'push_token': pushToken},
    );
    final id = response.data['id'] as String;
    await prefs.setString(key, id);
    await _listenForPushChanges(id);
    return id;
  }
}
