import 'package:home_rescue/screens/launchpad_screen.dart';
import 'package:home_rescue/screens/new_issue_screen.dart';
import 'package:home_rescue/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('appliance quick-start tiles seed the new issue appliance', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(440, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(theme: buildAppTheme(), home: const LaunchpadScreen()),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Dishwasher'));
    await tester.pumpAndSettle();

    final screen = tester.widget<NewIssueScreen>(find.byType(NewIssueScreen));
    expect(screen.appliance, 'dishwasher');
  });
}
