import 'package:flutter/material.dart';

import 'screens/login.dart';
import 'services/push_service.dart';

import 'package:firebase_messaging/firebase_messaging.dart';

final messengerKey = GlobalKey<ScaffoldMessengerState>();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await PushService.I.initialize();
  if (PushService.I.configured) {
    FirebaseMessaging.onMessage.listen((message) {
      messengerKey.currentState?.showSnackBar(
        SnackBar(
          content: Text(
            message.notification?.title ?? 'Nova atualização da família',
          ),
        ),
      );
    });
  }
  runApp(const JRFamilyApp());
}

class JRFamilyApp extends StatelessWidget {
  const JRFamilyApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    scaffoldMessengerKey: messengerKey,
    title: 'JR Family',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF00A9D6),
        brightness: Brightness.light,
      ),
      useMaterial3: true,
      cardTheme: const CardThemeData(margin: EdgeInsets.symmetric(vertical: 6)),
    ),
    darkTheme: ThemeData(
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF00D1FF),
        brightness: Brightness.dark,
      ),
      useMaterial3: true,
    ),
    themeMode: ThemeMode.system,
    home: const LoginScreen(),
  );
}
