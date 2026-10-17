String locationAge(String? value, {DateTime? now}) {
  final time = DateTime.tryParse(value ?? '');
  if (time == null) return 'Sem localização';
  final age = (now ?? DateTime.now()).toUtc().difference(time.toUtc());
  if (age.isNegative) return 'Horário do dispositivo inconsistente';
  if (age.inSeconds < 60) return 'Atualizado agora';
  if (age.inMinutes < 60)
    return 'Última atualização há ${age.inMinutes} minutos';
  return 'Última atualização há ${age.inHours} horas';
}
