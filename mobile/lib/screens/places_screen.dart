import 'package:flutter/material.dart';

import '../services/api.dart';
import '../services/location_service.dart';

class PlacesScreen extends StatefulWidget {
  final String familyId;
  final bool guardian;
  const PlacesScreen({
    super.key,
    required this.familyId,
    required this.guardian,
  });
  @override
  State<PlacesScreen> createState() => _PlacesScreenState();
}

class _PlacesScreenState extends State<PlacesScreen> {
  List<Map<String, dynamic>> items = [];

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    final response = await Api.I.dio.get(
      '/families/${widget.familyId}/geofences',
    );
    if (!mounted) return;
    setState(() {
      items = List<Map<String, dynamic>>.from(
        (response.data['items'] as List).map(
          (e) => Map<String, dynamic>.from(e),
        ),
      );
    });
  }

  Future<void> add() async {
    final name = TextEditingController(text: 'Escola');
    final radius = TextEditingController(text: '300');
    final position = await LocationShareService().currentOrNull();
    if (!mounted) return;
    if (position == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Não foi possível obter sua localização para criar o local.',
          ),
        ),
      );
      return;
    }
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Novo local seguro'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: name,
              decoration: const InputDecoration(labelText: 'Nome'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: radius,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Raio em metros'),
            ),
            const SizedBox(height: 12),
            const Text(
              'O centro será sua localização atual. Depois você poderá evoluir esta tela para selecionar o ponto diretamente no mapa.',
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    if (accepted != true) return;
    final parsedRadius =
        double.tryParse(radius.text.replaceAll(',', '.')) ?? 300;
    await Api.I.dio.post(
      '/families/${widget.familyId}/geofences',
      data: {
        'name': name.text.trim().isEmpty ? 'Local seguro' : name.text.trim(),
        'latitude': position.latitude,
        'longitude': position.longitude,
        'radius_m': parsedRadius.clamp(50, 5000),
      },
    );
    await load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Locais seguros')),
    floatingActionButton: widget.guardian
        ? FloatingActionButton(onPressed: add, child: const Icon(Icons.add))
        : null,
    body: RefreshIndicator(
      onRefresh: load,
      child: ListView(
        children: items
            .map(
              (g) => ListTile(
                leading: const Icon(Icons.place),
                title: Text('${g['name']}'),
                subtitle: Text('Raio: ${g['radius_m']} m'),
              ),
            )
            .toList(),
      ),
    ),
  );
}
