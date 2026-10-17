import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';

import 'package:flutter/foundation.dart';

class Api {
  Api._() {
    dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 20),
      ),
    );
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          options.baseUrl =
              await storage.read(key: 'api_base_url') ?? AppConfig.apiBaseUrl;
          final token = await storage.read(key: 'access_token');
          if (token != null) options.headers['Authorization'] = 'Bearer $token';
          handler.next(options);
        },
        onError: (error, handler) async {
          final request = error.requestOptions;
          if (error.response?.statusCode == 401 &&
              request.extra['retried'] != true &&
              ![
                '/auth/login',
                '/auth/register',
                '/auth/refresh',
              ].contains(request.path)) {
            try {
              await refresh();
              request.extra['retried'] = true;
              request.headers['Authorization'] =
                  'Bearer ${await storage.read(key: 'access_token')}';
              return handler.resolve(await dio.fetch<dynamic>(request));
            } catch (_) {
              /* Keep original authentication error. */
            }
          }
          handler.next(error);
        },
      ),
    );
  }
  static final Api I = Api._();
  late final Dio dio;
  final storage = const FlutterSecureStorage();
  Future<void>? _refreshing;
  Future<String> serverUrl() async =>
      await storage.read(key: 'api_base_url') ?? AppConfig.apiBaseUrl;
  Future<void> configureServer(String url) async {
    final uri = Uri.tryParse(url.trim());
    if (uri == null ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.scheme != 'https' && !(kDebugMode && uri.scheme == 'http'))) {
      throw ArgumentError('Informe o endereço HTTPS do servidor JR Family');
    }
    if (url != await serverUrl()) {
      await storage.delete(key: 'access_token');
      await storage.delete(key: 'refresh_token');
    }
    await storage.write(
      key: 'api_base_url',
      value: url.trim().replaceFirst(RegExp(r'/+$'), ''),
    );
  }

  Future<void> saveSession(Map<String, dynamic> data) async {
    await storage.write(
      key: 'access_token',
      value: data['access_token'] as String,
    );
    await storage.write(
      key: 'refresh_token',
      value: data['refresh_token'] as String,
    );
  }

  Future<void> refresh() =>
      _refreshing ??= _refresh().whenComplete(() => _refreshing = null);
  Future<void> _refresh() async {
    final token = await storage.read(key: 'refresh_token');
    if (token == null) throw StateError('Entre novamente');
    final response = await dio.post<dynamic>(
      '/auth/refresh',
      data: {'refresh_token': token},
    );
    await saveSession(Map<String, dynamic>.from(response.data as Map));
  }

  Future<void> logout() async {
    // Server revocation must succeed before reporting logout complete.
    await dio.post<dynamic>('/auth/logout');
    await storage.delete(key: 'access_token');
    await storage.delete(key: 'refresh_token');
  }
}
