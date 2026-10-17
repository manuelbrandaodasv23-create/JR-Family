import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jr_family/widgets/hold_sos.dart';

void main() {
  testWidgets('SOS requires three seconds and cancels early release', (
    tester,
  ) async {
    var sent = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: HoldSos(
            onActivate: () async {
              sent++;
            },
          ),
        ),
      ),
    );
    final finder = find.byType(HoldSos);
    await tester.tap(finder);
    await tester.pump(const Duration(seconds: 4));
    expect(sent, 0);
    final gesture = await tester.startGesture(tester.getCenter(finder));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 2900));
    expect(sent, 0);
    await tester.pump(const Duration(milliseconds: 200));
    expect(sent, 1);
    await gesture.up();
    await tester.pump();
  });
}
