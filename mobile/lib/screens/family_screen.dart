import 'package:flutter/material.dart';

import '../services/api.dart';

class FamilyScreen extends StatefulWidget {
  final String familyId;
  final bool guardian;
  const FamilyScreen({
    super.key,
    required this.familyId,
    required this.guardian,
  });
  @override
  State<FamilyScreen> createState() => _FamilyScreenState();
}

class _FamilyScreenState extends State<FamilyScreen> {
  List<Map<String, dynamic>> items = [];

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    final response = await Api.I.dio.get('/families/${widget.familyId}');
    if (!mounted) return;
    setState(() {
      items = List<Map<String, dynamic>>.from(
        (response.data['members'] as List).map(
          (e) => Map<String, dynamic>.from(e),
        ),
      );
    });
  }

  Future<void> createInvite() async {
    var role = 'dependent';
    final choice = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Novo convite'),
        content: StatefulBuilder(
          builder: (context, setInner) => DropdownButtonFormField<String>(
            initialValue: role,
            decoration: const InputDecoration(labelText: 'Perfil'),
            items: const [
              DropdownMenuItem(
                value: 'dependent',
                child: Text('Filho / dependente'),
              ),
              DropdownMenuItem(value: 'guardian', child: Text('Responsável')),
            ],
            onChanged: (value) => setInner(() => role = value ?? 'dependent'),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, role),
            child: const Text('Gerar código'),
          ),
        ],
      ),
    );
    if (choice == null) return;
    final response = await Api.I.dio.post(
      '/families/${widget.familyId}/invites',
      data: {'role': choice},
    );
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Código temporário'),
        content: SelectableText(
          '${response.data['code']}',
          style: Theme.of(context).textTheme.headlineMedium
              ?.copyWith(fontWeight: FontWeight.bold),
          textAlign: TextAlign.center,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Fechar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Minha Família'),
      actions: [
        if (widget.guardian)
          IconButton(
            onPressed: createInvite,
            icon: const Icon(Icons.person_add_alt_1),
            tooltip: 'Convidar',
          ),
      ],
    ),
    body: RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: items.map((member) {
          final location = member['latest_location'];
          final name = '${member['display_name']}';
          final stale = location?['stale'] == true;
          return Card(
            child: ListTile(
              leading: CircleAvatar(
                child: Text(
                  name.isEmpty ? '?' : name.substring(0, 1).toUpperCase(),
                ),
              ),
              title: Text(name),
              subtitle: Text(
                location == null
                    ? 'Localização indisponível'
                    : stale
                    ? 'Última localização conhecida: ${location['captured_at']}'
                    : 'Atualização: ${location['captured_at']}',
              ),
              trailing: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    member['sharing'] == true
                        ? Icons.location_on
                        : Icons.location_off,
                  ),
                  if (location?['battery_percent'] != null)
                    Text('🔋 ${location['battery_percent']}%'),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    ),
  );
}
