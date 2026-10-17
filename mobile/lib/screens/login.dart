import 'package:flutter/material.dart';

import '../services/api.dart';
import 'shell.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginState();
}

class _LoginState extends State<LoginScreen> {
  final server = TextEditingController();
  @override
  void initState() {
    super.initState();
    Api.I.serverUrl().then((url) {
      if (mounted) server.text = url;
    });
  }

  @override
  void dispose() {
    server.dispose();
    name.dispose();
    email.dispose();
    pass.dispose();
    super.dispose();
  }

  final name = TextEditingController();
  final email = TextEditingController();
  final pass = TextEditingController();
  bool busy = false;
  bool createAccount = false;
  String? error;

  Future<void> submit() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await Api.I.configureServer(server.text);
      final response = createAccount
          ? await Api.I.dio.post(
              '/auth/register',
              data: {
                'name': name.text.trim(),
                'email': email.text.trim(),
                'password': pass.text,
              },
            )
          : await Api.I.dio.post(
              '/auth/login',
              data: {'email': email.text.trim(), 'password': pass.text},
            );
      await Api.I.saveSession(Map<String, dynamic>.from(response.data as Map));
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const FamilyBootstrap()),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() {
        error = createAccount
            ? 'Não foi possível criar a conta. Verifique os dados e a conexão.'
            : 'Não foi possível entrar. Verifique e-mail, senha e servidor.';
      });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.family_restroom, size: 74),
                  const SizedBox(height: 16),
                  Text(
                    'JR Family',
                    style: Theme.of(context).textTheme.headlineLarge
                        ?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const Text('Sua família protegida e conectada.'),
                  const SizedBox(height: 28),
                  TextField(
                    controller: server,
                    keyboardType: TextInputType.url,
                    decoration: const InputDecoration(
                      labelText: 'Servidor JR Family (HTTPS)',
                      helperText: 'Endereço fornecido pelo administrador',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (createAccount) ...[
                    TextField(
                      controller: name,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(
                        labelText: 'Nome',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'E-mail',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: pass,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: 'Senha',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.all(10),
                      child: Text(
                        error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: busy ? null : submit,
                      child: Text(
                        busy
                            ? 'Aguarde...'
                            : createAccount
                            ? 'Criar conta'
                            : 'Entrar',
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => setState(() => createAccount = !createAccount),
                    child: Text(
                      createAccount ? 'Já tenho conta' : 'Criar uma conta',
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'O JR Family não funciona de forma oculta. O compartilhamento de localização é informado no aparelho e depende das permissões oficiais do sistema.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
