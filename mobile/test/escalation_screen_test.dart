import 'dart:convert';
import 'dart:io';

import 'package:appliance_fixer/api/api_client.dart';
import 'package:appliance_fixer/screens/escalation_screen.dart';
import 'package:appliance_fixer/theme.dart';
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

  Future<void> finishCaptures(WidgetTester tester) async {
    await tester.tap(find.text('Capture this shot'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Capture this shot'));
    await tester.pumpAndSettle();
  }

  testWidgets('renders escalation packet contents and guided shot',
      (tester) async {
    await pumpEscalation(tester);

    expect(find.text('Packet contents'), findsOneWidget);
    expect(find.text('Inspection video'), findsOneWidget);
    expect(find.text('2 of 4 shots'), findsOneWidget);
    expect(find.text('Shot 3 of 4'), findsOneWidget);
    expect(find.text('The compressor and start relay'), findsOneWidget);
    expect(find.text('Capture this shot'), findsOneWidget);
    expect(find.text('Contact LG'), findsOneWidget);
  });

  testWidgets('capturing advances until packet is ready', (tester) async {
    await pumpEscalation(tester);

    await finishCaptures(tester);

    expect(find.text('Share service packet'), findsOneWidget);
    expect(find.text('NOW ${String.fromCharCode(0x00B7)} GUIDED VIDEO'),
        findsNothing);
    expect(find.text('Packet ready to share.'), findsOneWidget);
    expect(find.textContaining('All shots captured'), findsOneWidget);
  });

  testWidgets('share invokes injected callback', (tester) async {
    String? shared;
    await pumpEscalation(
      tester,
      onShare: (text) async => shared = text,
    );

    await finishCaptures(tester);
    await tester.tap(find.text('Share service packet'));
    await tester.pumpAndSettle();

    expect(shared, isNotNull);
    expect(shared, contains('Service packet'));
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
