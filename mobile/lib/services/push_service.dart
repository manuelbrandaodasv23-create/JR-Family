import 'dart:async';
import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

@pragma('vm:entry-point')
Future<void> jrFamilyFirebaseBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp();
  } catch (_) {
    // O binário pode estar sem os arquivos Firebase durante desenvolvimento local.
  }
}

class PushService {
  PushService._();
  static final PushService I = PushService._();

  bool configured = false;
  String? token;
  StreamSubscription<String>? _refreshSub;
  final StreamController<String> _tokenChanges = StreamController.broadcast();
  Stream<String> get tokenChanges => _tokenChanges.stream;

  Future<void> initialize() async {
    FirebaseMessaging.onBackgroundMessage(jrFamilyFirebaseBackgroundHandler);
    try {
      await Firebase.initializeApp();
      configured = true;
      final messaging = FirebaseMessaging.instance;
      await messaging.setForegroundNotificationPresentationOptions(
        alert: true,
        badge: true,
        sound: true,
      );
      token = await _safeToken();
      await _refreshSub?.cancel();
      _refreshSub = messaging.onTokenRefresh.listen((value) {
        token = value;
        _tokenChanges.add(value);
      });
    } catch (_) {
      configured = false;
      token = null;
    }
  }

  Future<String?> _safeToken() async {
    if (!configured) return null;
    final messaging = FirebaseMessaging.instance;
    if (Platform.isIOS) {
      // No iOS o token APNs pode chegar depois da inicialização do Firebase.
      // Esperamos por um curto período sem bloquear indefinidamente o app.
      for (var i = 0; i < 8; i++) {
        final apns = await messaging.getAPNSToken();
        if (apns != null) break;
        await Future<void>.delayed(const Duration(milliseconds: 500));
      }
    }
    try {
      return await messaging.getToken();
    } catch (_) {
      return null;
    }
  }

  Future<String?> requestPermissionAndToken() async {
    if (!configured) return null;
    final settings = await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );
    if (settings.authorizationStatus == AuthorizationStatus.denied) return null;
    token = await _safeToken();
    return token;
  }
}
