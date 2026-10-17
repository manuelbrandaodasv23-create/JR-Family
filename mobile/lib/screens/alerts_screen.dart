import 'package:flutter/material.dart';

import '../services/api.dart';

class AlertsScreen extends StatefulWidget {
  final String familyId;
  const AlertsScreen({super.key, required this.familyId});
  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<Map<String, dynamic>> items = [];

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    final response = await Api.I.dio.get('/families/${widget.familyId}/alerts');
    if (!mounted) return;
    setState(() {
      items = List<Map<String, dynamic>>.from(
        (response.data['items'] as List).map(
          (e) => Map<String, dynamic>.from(e),
        ),
      );
    });
  }

  Future<void> markRead(String id) async {
    await Api.I.dio.patch('/families/${widget.familyId}/alerts/$id/read');
    await load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Alertas')),
    body: RefreshIndicator(
      onRefresh: load,
      child: ListView(
        children: items.map((alert) {
          final isSos = alert['kind'] == 'sos';
          final unread = alert['read_at'] == null;
          return ListTile(
            leading: Icon(
              isSos ? Icons.sos : Icons.notifications_active,
              color: isSos ? Theme.of(context).colorScheme.error : null,
            ),
            title: Text(
              '${alert['title']}',
              style: TextStyle(
                fontWeight: unread ? FontWeight.bold : FontWeight.normal,
              ),
            ),
            subtitle: Text('${alert['message']}\n${alert['created_at']}'),
            isThreeLine: true,
            trailing: unread
                ? IconButton(
                    onPressed: () => markRead(alert['id']),
                    icon: const Icon(Icons.done),
                  )
                : null,
          );
        }).toList(),
      ),
    ),
  );
}
