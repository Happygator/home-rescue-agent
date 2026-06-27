import 'dart:convert';
import 'dart:io';

import 'package:home_rescue/api/api_client.dart';
import 'package:home_rescue/screens/escalation_screen.dart';
import 'package:home_rescue/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  ApiClient fixtureClient() {
    final detailJson =
        File('test/fixtures/issue_detail_escalated.json').readAsStringSync();
    final escalateJson =
        File('test/fixtures/escalate_response.json').readAsStringSync();
    return ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        if (request.method == 'POST' &&
            request.url.path.endsWith('/escalate')) {
          return http.Response.bytes(utf8.encode(escalateJson), 200);
        }
        return http.Response.bytes(utf8.encode(detailJson), 200);
      }),
    );
  }

  Widget app({
    Future<void> Function(String shareText)? onShare,
    Future<void> Function(String recipient)? onContact,
  }) =>
      MaterialApp(
        theme: buildAppTheme(),
        home: EscalationScreen(
          caseId: 'case-9c4f7a02',
          client: fixtureClient(),
          onShare: onShare,
          onContact: onContact,
        ),
      );

  Future<void> pumpEscalation(
    WidgetTester tester, {
    Future<void> Function(String shareText)? onShare,
    Future<void> Function(String recipient)? onContact,
  }) async {
    await tester.binding.setSurfaceSize(const Size(440, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(app(onShare: onShare, onContact: onContact));
    await tester.pumpAndSettle();
  }

  testWidgets('renders escalation packet contents and escalation steps',
      (tester) async {
    await pumpEscalation(tester);

    expect(find.text('Packet contents'), findsOneWidget);
    expect(find.text('Escalation steps'), findsOneWidget);
    expect(find.text('0 of 4 done'), findsOneWidget);
    expect(
      find.text('NOW ${String.fromCharCode(0x00B7)} ESCALATION STEPS'),
      findsOneWidget,
    );
    expect(
      find.text('Note the symptom and any error code shown on the display.'),
      findsOneWidget,
    );
    expect(find.text('Share service packet'), findsOneWidget);
    expect(find.text('Contact LG'), findsOneWidget);
  });

  testWidgets('tapping a step toggles it done and updates progress',
      (tester) async {
    await pumpEscalation(tester);

    expect(find.text('0 of 4 done'), findsOneWidget);

    await tester.tap(
      find.text('Check that the appliance is plugged in and the outlet has power.'),
    );
    await tester.pumpAndSettle();

    expect(find.text('1 of 4 done'), findsOneWidget);
    expect(find.text('Steps complete.'), findsNothing);
  });

  testWidgets('share invokes injected callback', (tester) async {
    String? shared;
    await pumpEscalation(
      tester,
      onShare: (text) async => shared = text,
    );

    await tester.tap(find.text('Share service packet'));
    await tester.pumpAndSettle();

    expect(shared, isNotNull);
    expect(shared, contains('Service packet'));
    expect(shared, contains('escalation step'));
  });

  testWidgets('contact invokes injected callback', (tester) async {
    String? contacted;
    await pumpEscalation(
      tester,
      onContact: (recipient) async => contacted = recipient,
    );

    await tester.tap(find.text('Contact LG'));
    await tester.pumpAndSettle();

    expect(contacted, 'support@lg.com');
  });
}
