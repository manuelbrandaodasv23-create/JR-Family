import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api.dart';

class OfflineLocationQueue {
  static const _key = 'jr_pending_locations_v2';
  static const _storage = FlutterSecureStorage();
  static Future<void> _tail = Future<void>.value();
  Future<T> _locked<T>(Future<T> Function() action) {
    final next = _tail.then((_) => action());
    _tail = next.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return next;
  }

  Future<List<Map<String, dynamic>>> _load() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('jr_pending_locations_v1');
    final raw = await _storage.read(key: _key);
    if (raw == null) return [];
    return (jsonDecode(raw) as List)
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<void> _save(List<Map<String, dynamic>> items) => _storage.write(
    key: _key,
    value: jsonEncode(
      items.length > 250 ? items.sublist(items.length - 250) : items,
    ),
  );
  Future<void> clear() => _locked(() => _storage.delete(key: _key));
  Future<void> enqueue(String deviceId, Map<String, dynamic> payload) =>
      _locked(() async {
        final items = await _load();
        items.add({'device_id': deviceId, 'payload': payload});
        await _save(items);
      });
  Future<int> flush() => _locked(() async {
    final items = await _load();
    var sent = 0;
    while (items.isNotEmpty) {
      final item = items.first;
      final captured = DateTime.tryParse(
        item['payload']['captured_at'] as String? ?? '',
      );
      if (captured == null ||
          DateTime.now().toUtc().difference(captured).inHours > 24) {
        items.removeAt(0);
        await _save(items);
        continue;
      }
      try {
        await Api.I.dio.post<dynamic>(
          '/devices/${item['device_id']}/locations',
          data: item['payload'],
        );
        sent++;
      } on DioException catch (e) {
        if (![403, 404, 409, 422].contains(e.response?.statusCode)) break;
        // Never retry revoked sharing or an unauthorized device.
      }
      items.removeAt(0);
      await _save(items);
    }
    return sent;
  });
}
