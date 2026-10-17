import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../config.dart';
import '../services/api.dart';

class HistoryScreen extends StatefulWidget {
  final String familyId, memberId, name;
  const HistoryScreen({
    super.key,
    required this.familyId,
    required this.memberId,
    required this.name,
  });
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> items = [];
  String period = 'today';
  bool loading = false;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    DateTime start = today, end = now;
    if (period == 'yesterday') {
      start = today.subtract(const Duration(days: 1));
      end = today;
    }
    if (period == 'week') start = now.subtract(const Duration(days: 7));
    if (period == 'custom') {
      final range = await showDateRangePicker(
        context: context,
        firstDate: today.subtract(const Duration(days: 29)),
        lastDate: today,
      );
      if (range == null || !mounted) return;
      start = range.start;
      end = range.end.add(const Duration(days: 1));
    }
    if (!mounted) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await Api.I.dio.get<dynamic>(
        '/families/${widget.familyId}/members/${widget.memberId}/locations',
        queryParameters: {
          'start': start.toUtc().toIso8601String(),
          'end': end.toUtc().toIso8601String(),
        },
      );
      if (mounted)
        setState(
          () => items = (result.data['items'] as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList(),
        );
    } catch (_) {
      if (mounted)
        setState(() => error = 'Não foi possível carregar o histórico.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final points = items
        .map(
          (e) => LatLng(
            (e['latitude'] as num).toDouble(),
            (e['longitude'] as num).toDouble(),
          ),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(title: Text('Histórico • ${widget.name}')),
      body: Column(
        children: [
          DropdownButton<String>(
            value: period,
            items: const [
              DropdownMenuItem(value: 'today', child: Text('Hoje')),
              DropdownMenuItem(value: 'yesterday', child: Text('Ontem')),
              DropdownMenuItem(value: 'week', child: Text('Últimos 7 dias')),
              DropdownMenuItem(
                value: 'custom',
                child: Text('Período personalizado'),
              ),
            ],
            onChanged: loading
                ? null
                : (v) {
                    setState(() => period = v!);
                    load();
                  },
          ),
          if (loading) const LinearProgressIndicator(),
          if (error != null) Text(error!),
          if (points.length >= 2)
            SizedBox(
              height: 220,
              child: FlutterMap(
                key: ValueKey('${period}_${points.first}'),
                options: MapOptions(
                  initialCenter: points.first,
                  initialZoom: 13,
                ),
                children: [
                  TileLayer(
                    urlTemplate: AppConfig.mapTileUrl,
                    userAgentPackageName: 'com.jrfamily.app',
                  ),
                  PolylineLayer(
                    polylines: [
                      Polyline(
                        points: points,
                        strokeWidth: 4,
                        color: Colors.cyan,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          if (points.length >= 2) Text(AppConfig.mapAttribution),
          Expanded(
            child: items.isEmpty
                ? const Center(child: Text('Sem registros no período.'))
                : ListView.builder(
                    itemCount: items.length,
                    itemBuilder: (context, i) {
                      final item = items[i];
                      final date = DateTime.tryParse(
                        item['captured_at'] as String? ?? '',
                      )?.toLocal();
                      return ListTile(
                        leading: const Icon(Icons.location_on),
                        title: Text(date?.toString() ?? 'Horário indisponível'),
                        subtitle: Text(
                          'Precisão: ${item['accuracy_m'] ?? '—'} m • Bateria: ${item['battery_percent'] ?? '—'}%',
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
