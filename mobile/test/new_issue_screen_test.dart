import 'dart:async';
import 'dart:convert';

import 'package:home_rescue/api/api_client.dart';
import 'package:home_rescue/screens/new_issue_screen.dart';
import 'package:home_rescue/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const baseUrl = 'http://test';

  // A diagnosing detail so navigating to the chat screen does NOT trigger the intake auto-kickoff
  // (which only fires for an `intake` case) - keeps these tests focused on the composer.
  Map<String, dynamic> detail({
    List<Map<String, dynamic>> messages = const [],
  }) => {
    'case_id': 'case-new123',
    'title': 'New · Refrigerator',
    'brand': null,
    'appliance': 'Refrigerator',
    'model_number': null,
    'status': 'diagnosing',
    'symptom': 'Fresh food section is warm',
    'error_code': null,
    'diagnosis': null,
    'steps': <dynamic>[],
    'next_step': '',
    'media': <dynamic>[],
    'messages': messages,
    'escalation': null,
    'created_at': '',
    'updated_at': '',
  };

  ApiClient mockClient(
    List<String> calls, {
    void Function(String body)? onUpdate,
    void Function(String body)? onCreate,
  }) {
    return ApiClient(
      baseUrl: baseUrl,
      client: MockClient.streaming((req, body) async {
        calls.add('${req.method} ${req.url.path}');
        if (req.method == 'POST' && req.url.path == '/api/issues') {
          if (onCreate != null) onCreate(await body.bytesToString());
          return _jsonStream({'case_id': 'case-new123'});
        }
        if (req.method == 'POST' &&
            req.url.path == '/api/issues/case-new123/media') {
          return _jsonStream({'ref': 'symptom-x.bin'});
        }
        if (req.method == 'POST' && req.url.path == '/api/issues/case-new123') {
          if (onUpdate != null) onUpdate(await body.bytesToString());
          return _jsonStream(detail());
        }
        // GET detail (after navigation), and any other call.
        return _jsonStream(detail());
      }),
    );
  }

  Future<void> pumpComposer(
    WidgetTester tester,
    ApiClient client, {
    String? appliance,
    Future<List<int>?> Function()? capturePhoto,
  }) async {
    await tester.binding.setSurfaceSize(const Size(440, 2200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: NewIssueScreen(
          appliance: appliance,
          client: client,
          capturePhoto: capturePhoto,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  FilledButton startButton(WidgetTester tester) => tester.widget<FilledButton>(
    find.widgetWithText(FilledButton, 'Start diagnosis'),
  );

  testWidgets(
    'does NOT create the case on open and Start is disabled until described',
    (tester) async {
      final calls = <String>[];
      await pumpComposer(tester, mockClient(calls));

      // No network on open - the old scripted intake created the case immediately; this one waits.
      expect(calls, isEmpty);
      expect(startButton(tester).onPressed, isNull);

      await tester.enterText(
        find.byType(TextField),
        'Fresh food section is warm',
      );
      await tester.pump();
      expect(startButton(tester).onPressed, isNotNull);
    },
  );

  testWidgets('description hint is neutral when no appliance is selected', (
    tester,
  ) async {
    final calls = <String>[];
    await pumpComposer(tester, mockClient(calls));

    expect(
      find.text('e.g. Describe what the appliance is doing wrong...'),
      findsOneWidget,
    );
    expect(find.textContaining('fridge'), findsNothing);
  });

  testWidgets('description hint is tailored to the selected appliance', (
    tester,
  ) async {
    final calls = <String>[];
    await pumpComposer(tester, mockClient(calls), appliance: 'Dishwasher');

    expect(
      find.text('e.g. The dishwasher runs but dishes come out dirty...'),
      findsOneWidget,
    );
    expect(find.textContaining('fridge'), findsNothing);
  });

  testWidgets(
    'creates the case, seeds the description as the first user message, navigates',
    (tester) async {
      final calls = <String>[];
      String? createBody;
      String? updateBody;
      final client = mockClient(
        calls,
        onCreate: (b) => createBody = b,
        onUpdate: (b) => updateBody = b,
      );

      await pumpComposer(tester, client);
      await tester.enterText(
        find.byType(TextField),
        'Fresh food section is warm',
      );
      await tester.pump();
      await tester.tap(find.text('Start diagnosis'));
      await tester.pumpAndSettle();

      // Order: create, then patch with the seeded message, then the chat screen loads.
      final createIndex = calls.indexOf('POST /api/issues');
      final updateIndex = calls.indexOf('POST /api/issues/case-new123');
      expect(createIndex, greaterThanOrEqualTo(0));
      expect(updateIndex, greaterThan(createIndex));
      expect(calls, contains('GET /api/issues/case-new123'));

      expect(jsonDecode(createBody!)['symptom'], 'Fresh food section is warm');

      final decoded = jsonDecode(updateBody!) as Map<String, dynamic>;
      final msgs = (decoded['messages'] as List).cast<Map<String, dynamic>>();
      expect(msgs.length, 1);
      expect(msgs.first['role'], 'user');
      expect(msgs.first['text'], 'Fresh food section is warm');
      expect(msgs.first.containsKey('media_ref'), isFalse);
    },
  );

  testWidgets('passes the seeded appliance when creating the case', (
    tester,
  ) async {
    final calls = <String>[];
    String? createBody;
    final client = mockClient(calls, onCreate: (b) => createBody = b);

    await pumpComposer(tester, client, appliance: 'Dishwasher');
    await tester.enterText(
      find.byType(TextField),
      'Water is pooling underneath',
    );
    await tester.pump();
    await tester.tap(find.text('Start diagnosis'));
    await tester.pumpAndSettle();

    final decoded = jsonDecode(createBody!) as Map<String, dynamic>;
    expect(decoded['appliance'], 'Dishwasher');
    expect(decoded['symptom'], 'Water is pooling underneath');
  });

  testWidgets(
    'attaching a photo uploads media and seeds it as media_ref on the first message',
    (tester) async {
      final calls = <String>[];
      String? updateBody;
      final client = mockClient(calls, onUpdate: (b) => updateBody = b);

      await pumpComposer(tester, client, capturePhoto: () async => [1, 2, 3]);

      await tester.tap(find.text('Add a photo'));
      await tester.pumpAndSettle();
      expect(find.text('Photo attached'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'Compressor is loud');
      await tester.pump();
      await tester.tap(find.text('Start diagnosis'));
      await tester.pumpAndSettle();

      final mediaIndex = calls.indexOf('POST /api/issues/case-new123/media');
      final updateIndex = calls.indexOf('POST /api/issues/case-new123');
      expect(mediaIndex, greaterThanOrEqualTo(0));
      expect(updateIndex, greaterThan(mediaIndex));

      final msgs = (jsonDecode(updateBody!)['messages'] as List)
          .cast<Map<String, dynamic>>();
      expect(msgs.first['media_ref'], 'symptom-x.bin');
    },
  );

  testWidgets('removing an attached photo clears it', (tester) async {
    final calls = <String>[];
    await pumpComposer(
      tester,
      mockClient(calls),
      capturePhoto: () async => [1, 2, 3],
    );

    await tester.tap(find.text('Add a photo'));
    await tester.pumpAndSettle();
    expect(find.text('Photo attached'), findsOneWidget);

    await tester.tap(find.text('Remove'));
    await tester.pumpAndSettle();
    expect(find.text('Photo attached'), findsNothing);
    expect(find.text('Add a photo'), findsOneWidget);
  });
}

http.StreamedResponse _jsonStream(Map<String, dynamic> body) {
  return http.StreamedResponse(
    Stream.value(utf8.encode(jsonEncode(body))),
    200,
    headers: {'content-type': 'application/json'},
  );
}
