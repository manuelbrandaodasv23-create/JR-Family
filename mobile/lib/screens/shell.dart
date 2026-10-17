import 'package:flutter/material.dart';

import '../services/api.dart';
import 'map_screen.dart';
import 'family_screen.dart';
import 'alerts_screen.dart';
import 'places_screen.dart';
import 'settings_screen.dart';

class FamilyBootstrap extends StatefulWidget {
  const FamilyBootstrap({super.key});
  @override
  State<FamilyBootstrap> createState() => _FamilyBootstrapState();
}

class _FamilyBootstrapState extends State<FamilyBootstrap> {
  String? familyId;
  String? memberId;
  String? role;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() => loading = true);
    try {
      final response = await Api.I.dio.get('/me');
      final memberships = List<Map<String, dynamic>>.from(
        (response.data['memberships'] as List).map(
          (e) => Map<String, dynamic>.from(e),
        ),
      );
      if (memberships.isNotEmpty) {
        familyId = memberships.first['family_id'];
        memberId = memberships.first['member_id'];
        role = memberships.first['role'];
      } else {
        familyId = null;
        memberId = null;
        role = null;
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading)
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (familyId == null) return FamilyOnboarding(onChanged: load);
    return HomeShell(
      familyId: familyId!,
      memberId: memberId!,
      role: role ?? 'guardian',
    );
  }
}

class FamilyOnboarding extends StatefulWidget {
  final Future<void> Function() onChanged;
  const FamilyOnboarding({super.key, required this.onChanged});
  @override
  State<FamilyOnboarding> createState() => _FamilyOnboardingState();
}

class _FamilyOnboardingState extends State<FamilyOnboarding> {
  final familyName = TextEditingController(text: 'Minha Família');
  final inviteCode = TextEditingController();
  final displayName = TextEditingController();
  bool busy = false;

  Future<void> create() async {
    setState(() => busy = true);
    try {
      await Api.I.dio.post(
        '/families',
        data: {
          'name': familyName.text.trim().isEmpty
              ? 'Minha Família'
              : familyName.text.trim(),
        },
      );
      await widget.onChanged();
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> join() async {
    setState(() => busy = true);
    try {
      await Api.I.dio.post(
        '/invites/join',
        data: {
          'code': inviteCode.text.trim(),
          'display_name': displayName.text.trim(),
        },
      );
      await widget.onChanged();
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Não foi possível entrar na família: $e')),
        );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('JR Family')),
    body: ListView(
      padding: const EdgeInsets.all(18),
      children: [
        Text(
          'Começar',
          style: Theme.of(context).textTheme.headlineSmall
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Sou responsável',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: familyName,
                  decoration: const InputDecoration(
                    labelText: 'Nome da família',
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: busy ? null : create,
                  icon: const Icon(Icons.add),
                  label: const Text('Criar família'),
                ),
              ],
            ),
          ),
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Recebi um convite',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: inviteCode,
                  keyboardType: TextInputType.text,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                    labelText: 'Código do convite',
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: displayName,
                  decoration: const InputDecoration(
                    labelText: 'Nome que aparecerá na família',
                  ),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: busy ? null : join,
                  icon: const Icon(Icons.group_add),
                  label: const Text('Entrar com convite'),
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

class HomeShell extends StatefulWidget {
  final String familyId;
  final String memberId;
  final String role;
  const HomeShell({
    super.key,
    required this.familyId,
    required this.memberId,
    required this.role,
  });
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    final guardian = widget.role == 'guardian';
    final pages = [
      MapScreen(familyId: widget.familyId),
      FamilyScreen(familyId: widget.familyId, guardian: guardian),
      AlertsScreen(familyId: widget.familyId),
      PlacesScreen(familyId: widget.familyId, guardian: guardian),
      SettingsScreen(
        familyId: widget.familyId,
        memberId: widget.memberId,
        role: widget.role,
      ),
    ];
    return Scaffold(
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.map), label: 'Mapa'),
          NavigationDestination(
            icon: Icon(Icons.family_restroom),
            label: 'Família',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications),
            label: 'Alertas',
          ),
          NavigationDestination(icon: Icon(Icons.place), label: 'Locais'),
          NavigationDestination(icon: Icon(Icons.settings), label: 'Config.'),
        ],
      ),
    );
  }
}
