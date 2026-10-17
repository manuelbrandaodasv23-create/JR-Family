import 'dart:async';

import 'package:flutter/material.dart';

import '../services/location_age.dart';
import 'history_screen.dart';

import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../config.dart';
import '../services/api.dart';

class MapScreen extends StatefulWidget {
  final String familyId;
  const MapScreen({super.key, required this.familyId});
  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  List<Map<String, dynamic>> members = [];
  List<Map<String, dynamic>> fences = [];
  Timer? refreshTimer;
  @override
  void dispose() {
    refreshTimer?.cancel();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    load();
    refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) => load());
  }

  Future<void> load() async {
    try {
      final response = await Api.I.dio.get('/families/${widget.familyId}');
      final places = await Api.I.dio.get(
        '/families/${widget.familyId}/geofences',
      );
      if (!mounted) return;
      setState(() {
        fences = (places.data['items'] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        members = List<Map<String, dynamic>>.from(
          (response.data['members'] as List).map(
            (e) => Map<String, dynamic>.from(e),
          ),
        );
      });
    } catch (_) {
      /* Keep last fix with its original timestamp. */
    }
  }

  @override
  Widget build(BuildContext context) {
    final located = members.where((m) => m['latest_location'] != null).toList();
    final center = located.isEmpty
        ? const LatLng(-8.7612, -63.9004)
        : LatLng(
            (located.first['latest_location']['latitude'] as num).toDouble(),
            (located.first['latest_location']['longitude'] as num).toDouble(),
          );
    return Scaffold(
      appBar: AppBar(
        title: const Text('JR Family • Mapa'),
        actions: [IconButton(onPressed: load, icon: const Icon(Icons.refresh))],
      ),
      body: Stack(
        children: [
          FlutterMap(
            options: MapOptions(initialCenter: center, initialZoom: 13),
            children: [
              TileLayer(
                urlTemplate: AppConfig.mapTileUrl,
                userAgentPackageName: 'com.jrfamily.app',
              ),
              CircleLayer(
                circles: fences
                    .where((f) => f['enabled'] == true)
                    .map(
                      (f) => CircleMarker(
                        point: LatLng(
                          (f['latitude'] as num).toDouble(),
                          (f['longitude'] as num).toDouble(),
                        ),
                        radius: (f['radius_m'] as num).toDouble(),
                        useRadiusInMeter: true,
                        color: Colors.cyan.withValues(alpha: .15),
                        borderColor: Colors.cyan,
                        borderStrokeWidth: 2,
                      ),
                    )
                    .toList(),
              ),
              MarkerLayer(
                markers: located.map((member) {
                  final location = member['latest_location'];
                  final stale = location['stale'] == true;
                  return Marker(
                    point: LatLng(
                      (location['latitude'] as num).toDouble(),
                      (location['longitude'] as num).toDouble(),
                    ),
                    width: 190,
                    height: 120,
                    child: GestureDetector(
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => HistoryScreen(
                            familyId: widget.familyId,
                            memberId: member['id'] as String,
                            name: member['display_name'] as String,
                          ),
                        ),
                      ),
                      child: Column(
                        children: [
                          Text(
                            locationAge(location['captured_at'] as String?),
                            style: const TextStyle(fontSize: 11),
                          ),
                          Text(
                            'Bateria: ${location['battery_percent'] ?? '—'}%',
                            style: const TextStyle(fontSize: 11),
                          ),
                          Icon(
                            stale
                                ? Icons.location_disabled
                                : Icons.location_pin,
                            size: 40,
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.surface
                                  .withValues(alpha: .9),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              '${member['display_name']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            ],
          ),
          Positioned(
            left: 8,
            bottom: 8,
            child: Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                child: Text(
                  AppConfig.mapAttribution,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
