import 'dart:async';

import 'package:flutter/material.dart';

import '../widgets/hold_sos.dart';
import 'login.dart';

import 'package:geolocator/geolocator.dart';

import '../services/api.dart';
import '../services/device_service.dart';
import '../services/location_service.dart';
import '../services/push_service.dart';

class SettingsScreen extends StatefulWidget {
  final String familyId;
  final String memberId;
  final String role;
  const SettingsScreen({
    super.key,
    required this.familyId,
    required this.memberId,
    required this.role,
  });
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final location = LocationShareService();
  bool sharing = false;
  bool busy = false;
  String? deviceId;
  String status = 'Compartilhamento desativado';
  String mode = 'balanced';
  LocationPermission? permission;

  @override
  void initState() {
    super.initState();
    location.onError = (message) {
      if (mounted)
        setState(() {
          sharing = false;
          status = message;
        });
    };
  }

  @override
  void dispose() {
    location.onError = null;
    unawaited(location.stopLocal());
    super.dispose();
  }

  Future<void> prepareDevice() async {
    deviceId ??= await DeviceService.I.ensureDevice(
      familyId: widget.familyId,
      memberId: widget.memberId,
    );
  }

  Future<void> toggle(bool value) async {
    setState(() => busy = true);
    try {
      await prepareDevice();
      if (value) {
        await location.start(
          familyId: widget.familyId,
          deviceId: deviceId!,
          memberId: widget.memberId,
          mode: mode,
        );
        permission = await Geolocator.checkPermission();
        setState(() {
          status = permission == LocationPermission.always
              ? 'Localização compartilhada em segundo plano com responsáveis autorizados.'
              : 'Compartilhamento ativo. O sistema não concedeu acesso “Sempre”; atualizações em segundo plano podem ser limitadas.';
        });
      } else {
        await location.stop(familyId: widget.familyId, deviceId: deviceId!);
        setState(() => status = 'Compartilhamento desativado');
      }
      if (mounted) setState(() => sharing = value);
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> sos() async {
    final position = await location.currentOrNull();
    await Api.I.dio.post(
      '/families/${widget.familyId}/members/${widget.memberId}/sos',
      data: {'latitude': position?.latitude, 'longitude': position?.longitude},
    );
    if (mounted)
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('SOS enviado aos responsáveis.')),
      );
  }

  Future<void> openAppSettings() async {
    await Geolocator.openAppSettings();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Configurações')),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: SwitchListTile(
            value: sharing,
            onChanged: busy ? null : toggle,
            title: const Text('Compartilhar localização'),
            subtitle: Text(status),
            secondary: Icon(sharing ? Icons.location_on : Icons.location_off),
          ),
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Modo de localização',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                RadioListTile<String>(
                  value: 'economy',
                  groupValue: mode,
                  onChanged: sharing ? null : (v) => setState(() => mode = v!),
                  title: const Text('Economia'),
                  subtitle: const Text(
                    'Menos atualizações e menor consumo de bateria.',
                  ),
                ),
                RadioListTile<String>(
                  value: 'balanced',
                  groupValue: mode,
                  onChanged: sharing ? null : (v) => setState(() => mode = v!),
                  title: const Text('Equilibrado'),
                  subtitle: const Text('Boa precisão com consumo moderado.'),
                ),
                RadioListTile<String>(
                  value: 'high',
                  groupValue: mode,
                  onChanged: sharing ? null : (v) => setState(() => mode = v!),
                  title: const Text('Maior precisão'),
                  subtitle: const Text(
                    'Mais atualizações quando o sistema permitir.',
                  ),
                ),
              ],
            ),
          ),
        ),
        const Card(
          child: ListTile(
            leading: Icon(Icons.privacy_tip),
            title: Text('Quem pode ver minha localização'),
            subtitle: Text(
              'Somente membros autorizados da família, conforme o perfil e as permissões.',
            ),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.notifications_active),
            title: const Text('Notificações'),
            subtitle: Text(
              PushService.I.configured
                  ? 'Firebase configurado neste binário.'
                  : 'Firebase ainda não está configurado neste binário.',
            ),
          ),
        ),
        OutlinedButton.icon(
          onPressed: openAppSettings,
          icon: const Icon(Icons.settings),
          label: const Text('Abrir permissões do aparelho'),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 18),
          child: HoldSos(onActivate: sos),
        ),
        const Divider(height: 32),
        TextButton(
          onPressed: () async {
            final confirmed = await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Excluir minha conta?'),
                content: const Text(
                  'Seus dispositivos e histórico serão excluídos. Se você é titular de uma família, exclua-a primeiro pela administração da família.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancelar'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Excluir conta'),
                  ),
                ],
              ),
            );
            if (confirmed != true) return;
            try {
              await location.stopLocal();
              await Api.I.dio.delete<dynamic>('/me');
              await Api.I.storage.delete(key: 'access_token');
              await Api.I.storage.delete(key: 'refresh_token');
              if (!mounted) return;
              Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
                (_) => false,
              );
            } catch (_) {
              if (mounted)
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text(
                      'Exclusão não concluída. Verifique se você ainda é titular de uma família e se há conexão.',
                    ),
                  ),
                );
            }
          },
          child: const Text('Excluir minha conta'),
        ),

        OutlinedButton(
          onPressed: () async {
            try {
              if (deviceId != null)
                await location.stop(
                  familyId: widget.familyId,
                  deviceId: deviceId!,
                );
              await Api.I.logout();
              if (!mounted) return;
              Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
                (_) => false,
              );
            } catch (_) {
              if (mounted)
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text(
                      'Não foi possível encerrar a sessão no servidor. Tente novamente com conexão.',
                    ),
                  ),
                );
            }
          },
          child: const Text('Sair'),
        ),
      ],
    ),
  );
}
