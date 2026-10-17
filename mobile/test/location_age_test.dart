import 'package:flutter_test/flutter_test.dart';
import 'package:jr_family/services/location_age.dart';

void main() {
  test('Old locations are never reported as live', () {
    final now = DateTime.utc(2026, 10, 16, 12);
    expect(
      locationAge('2026-10-16T11:42:00Z', now: now),
      'Última atualização há 18 minutos',
    );
    expect(locationAge('2026-10-16T11:59:45Z', now: now), 'Atualizado agora');
    expect(locationAge(null, now: now), 'Sem localização');
    expect(
      locationAge('2026-10-16T13:00:00Z', now: now),
      'Horário do dispositivo inconsistente',
    );
  });
}
