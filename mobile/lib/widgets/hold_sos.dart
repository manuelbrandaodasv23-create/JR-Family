import 'dart:async';

import 'package:flutter/material.dart';

class HoldSos extends StatefulWidget {
  final Future<void> Function() onActivate;
  const HoldSos({super.key, required this.onActivate});
  @override
  State<HoldSos> createState() => _HoldSosState();
}

class _HoldSosState extends State<HoldSos> {
  Timer? timer;
  bool holding = false;
  bool sending = false;
  void cancel() {
    timer?.cancel();
    if (mounted) setState(() => holding = false);
  }

  void begin() {
    if (sending || holding) return;
    setState(() => holding = true);
    timer = Timer(const Duration(seconds: 3), () async {
      setState(() {
        holding = false;
        sending = true;
      });
      try {
        await widget.onActivate();
      } catch (_) {
        if (mounted)
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'SOS não enviado. Verifique a conexão ou ligue para seu responsável.',
              ),
            ),
          );
      } finally {
        if (mounted) setState(() => sending = false);
      }
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Semantics(
    label: 'SOS. Pressione e segure por três segundos',
    button: true,
    child: GestureDetector(
      onTapDown: (_) => begin(),
      onTapUp: (_) => cancel(),
      onTapCancel: cancel,
      child: Container(
        height: 72,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.error,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          sending
              ? 'Enviando SOS...'
              : holding
              ? 'Continue segurando...'
              : 'SOS • segure por 3 segundos',
          style: TextStyle(
            color: Theme.of(context).colorScheme.onError,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    ),
  );
}
