import 'dart:convert';
import 'dart:io';

import 'package:home_rescue/api/api_client.dart';
import 'package:home_rescue/screens/issue_detail_screen.dart';
import 'package:home_rescue/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  ApiClient fixtureClient() {
    final detailJson = File('test/fixtures/issue_detail_diagnosing.json').readAsStringSync();
    return ApiClient(
      baseUrl: 'http://test',
      client: MockClient.streaming((req, body) async {
        if (req.method == 'POST' && req.url.path.endsWith('/message')) {
          return http.StreamedResponse(
            Stream.value(utf8.encode(
              'data: {"type":"token","text":"Sure"}\n\n'
              'data: {"type":"done","status":"diagnosing"}\n\n',
            )),
            200,
            headers: {'content-type': 'text/event-stream'},
          );
        }
        return http.StreamedResponse(Stream.value(utf8.encode(detailJson)), 200);
      }),
    );
  }

  Widget app() => MaterialApp(
        theme: buildAppTheme(),
        home: IssueDetailScreen(caseId: 'case-7f3a9c21', client: fixtureClient()),
      );

  Future<void> pumpDetail(WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 2400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
  }

  testWidgets('loads and shows the summary', (tester) async {
    await pumpDetail(tester);

    expect(find.text('Case summary'), findsOneWidget);
    expect(find.textContaining('Fresh-food warm'), findsOneWidget);
    // The model is shown inside the summary (not only in the faint top sub-row).
    expect(find.textContaining('Model: Samsung'), findsOneWidget);
    expect(find.textContaining('RF28R7201'), findsWidgets);
    expect(find.text('Escalate to a pro'), findsOneWidget);
  });

  testWidgets('step checklist shows pending third step', (tester) async {
    await pumpDetail(tester);

    // The instruction appears in both the summary checklist and the seeded chat transcript;
    // only the summary row carries the "pending" outcome label.
    expect(find.textContaining('Clean condenser coils'), findsWidgets);
    expect(find.textContaining('Clean condenser coils ${String.fromCharCode(0x2014)} pending'), findsOneWidget);
  });

  testWidgets('safety bubble is seeded', (tester) async {
    await pumpDetail(tester);

    expect(find.textContaining('needs a pro'), findsOneWidget);
  });

  testWidgets('sending a message streams an agent response', (tester) async {
    await pumpDetail(tester);

    await tester.enterText(find.byType(TextField), 'Can I try one more thing?');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    expect(find.text('Can I try one more thing?'), findsOneWidget);
    expect(find.textContaining('Sure'), findsOneWidget);
  });

  testWidgets('renders the persisted transcript instead of a synthetic seed', (tester) async {
    const detail = {
      'case_id': 'case-xyz',
      'title': 'Samsung · Refrigerator',
      'brand': 'Samsung',
      'appliance': 'Refrigerator',
      'model_number': 'RF28R7201',
      'status': 'diagnosing',
      'symptom': 'fridge is 50F',
      'error_code': null,
      'diagnosis': null,
      'steps': <dynamic>[],
      'next_step': 'Answer below to start diagnosis.',
      'media': <dynamic>[],
      'messages': [
        {'role': 'user', 'text': 'fridge is 50F', 'ts': null},
        {'role': 'agent', 'text': 'Got it, the fridge is warm.', 'ts': null},
      ],
      'escalation': null,
      'created_at': '',
      'updated_at': '',
    };
    final client = ApiClient(
      baseUrl: 'http://test',
      client: MockClient.streaming((req, body) async =>
          http.StreamedResponse(Stream.value(utf8.encode(jsonEncode(detail))), 200)),
    );

    await tester.binding.setSurfaceSize(const Size(420, 2400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MaterialApp(
      theme: buildAppTheme(),
      home: IssueDetailScreen(caseId: 'case-xyz', client: client),
    ));
    await tester.pumpAndSettle();

    expect(find.text('fridge is 50F'), findsOneWidget);
    expect(find.text('Got it, the fridge is warm.'), findsOneWidget);
    // The synthetic "picking up where we left off" seed must NOT appear when real history exists.
    expect(find.textContaining('picking up where we left off'), findsNothing);
  });

  testWidgets('auto-kickoff streams a first fix for a fresh intake case', (tester) async {
    var startCalls = 0;
    const detail = {
      'case_id': 'case-fresh',
      'title': 'Samsung · Refrigerator',
      'brand': 'Samsung',
      'appliance': 'Refrigerator',
      'model_number': 'RF28R7201',
      'status': 'intake',
      'symptom': 'fridge is 50F',
      'error_code': null,
      'diagnosis': null,
      'steps': <dynamic>[],
      'next_step': 'Continue in the chat for your next step.',
      'media': <dynamic>[],
      'messages': [
        {'role': 'user', 'text': 'fridge is 50F', 'ts': null},
      ],
      'escalation': null,
      'created_at': '',
      'updated_at': '',
    };
    final client = ApiClient(
      baseUrl: 'http://test',
      client: MockClient.streaming((req, body) async {
        if (req.method == 'POST' && req.url.path.endsWith('/start')) {
          startCalls++;
          return http.StreamedResponse(
            Stream.value(utf8.encode(
              'data: {"type":"token","text":"Check the temperature setting"}\n\n'
              'data: {"type":"done","status":"diagnosing"}\n\n',
            )),
            200,
            headers: {'content-type': 'text/event-stream'},
          );
        }
        return http.StreamedResponse(Stream.value(utf8.encode(jsonEncode(detail))), 200);
      }),
    );

    await tester.binding.setSurfaceSize(const Size(420, 2400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MaterialApp(
      theme: buildAppTheme(),
      home: IssueDetailScreen(caseId: 'case-fresh', client: client),
    ));
    await tester.pumpAndSettle();

    expect(startCalls, 1);
    expect(find.textContaining('Check the temperature setting'), findsOneWidget);
  });
}
