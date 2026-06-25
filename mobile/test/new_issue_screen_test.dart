import 'dart:convert';

import 'package:appliance_fixer/api/api_client.dart';
import 'package:appliance_fixer/screens/new_issue_screen.dart';
import 'package:appliance_fixer/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const baseUrl = 'http://test';

  ApiClient mockClient(List<String> calls) {
    return ApiClient(
      baseUrl: baseUrl,
      client: MockClient.streaming((req, body) async {
        calls.add('${req.method} ${req.url.path}');

        if (req.method == 'POST' && req.url.path == '/api/issues') {
          return _jsonStream({'case_id': 'case-new123'});
        }
        if (req.method == 'POST' && req.url.path == '/api/issues/case-new123/media') {
          return _jsonStream({'ref': 'plate-x.bin'});
        }
        if (req.method == 'POST' && req.url.path == '/api/issues/case-new123/plate') {
          return _jsonStream({
            'brand': 'Samsung',
            'model': 'RF28R7201',
            'error_code': null,
          });
        }
        return _jsonStream(<String, dynamic>{});
      }),
    );
  }

  Widget app({
    required List<String> calls,
    Future<List<int>?> Function()? capturePlate,
  }) {
    return MaterialApp(
      theme: buildAppTheme(),
      home: NewIssueScreen(client: mockClient(calls), capturePlate: capturePlate),
    );
  }

  Future<void> pumpNewIssue(
    WidgetTester tester, {
    required List<String> calls,
    Future<List<int>?> Function()? capturePlate,
  }) async {
    await tester.binding.setSurfaceSize(const Size(440, 2200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(app(calls: calls, capturePlate: capturePlate));
    await tester.pumpAndSettle();
  }

  testWidgets('creates the case FIRST', (tester) async {
    final calls = <String>[];

    await pumpNewIssue(tester, calls: calls, capturePlate: () async => [1, 2, 3]);

    expect(calls.first, 'POST /api/issues');
    expect(find.text('INTAKE'), findsOneWidget);
    expect(find.text('Case summary'), findsOneWidget);
    expect(find.text("Hi! I'm your Appliance Fixer assistant."), findsOneWidget);
  });

  testWidgets('scan posts media then plate to the created id, and auto-fills', (tester) async {
    final calls = <String>[];

    await pumpNewIssue(tester, calls: calls, capturePlate: () async => [1, 2, 3]);
    await tester.tap(find.byIcon(Icons.photo_camera_outlined));
    await tester.pumpAndSettle();

    final mediaIndex = calls.indexOf('POST /api/issues/case-new123/media');
    final plateIndex = calls.indexOf('POST /api/issues/case-new123/plate');
    expect(mediaIndex, greaterThanOrEqualTo(0));
    expect(plateIndex, greaterThanOrEqualTo(0));
    expect(mediaIndex, lessThan(plateIndex));
    expect(find.textContaining('RF28R7201'), findsWidgets);
  });

  testWidgets('camera-denied falls back to manual', (tester) async {
    final calls = <String>[];

    await pumpNewIssue(tester, calls: calls, capturePlate: () async => null);
    await tester.tap(find.byIcon(Icons.photo_camera_outlined));
    await tester.pumpAndSettle();

    expect(find.textContaining('type your model'), findsOneWidget);
    expect(
      find.byWidgetPredicate(
        (widget) =>
            widget is TextField &&
            widget.decoration?.hintText?.toLowerCase().contains('model') == true,
      ),
      findsOneWidget,
    );
    expect(calls, isNot(contains('POST /api/issues/case-new123/media')));
    expect(calls, isNot(contains('POST /api/issues/case-new123/plate')));
  });

  testWidgets('typing a symptom enables Start', (tester) async {
    final calls = <String>[];

    // Inject a deterministic plate capture (the real default is the device camera, which
    // returns null in a widget test).
    await pumpNewIssue(tester, calls: calls, capturePlate: () async => [1, 2, 3]);
    await tester.tap(find.byIcon(Icons.photo_camera_outlined));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Fresh food section is warm');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    expect(find.text('Start diagnosis'), findsOneWidget);
  });
}

http.StreamedResponse _jsonStream(Map<String, dynamic> body) {
  return http.StreamedResponse(
    Stream.value(utf8.encode(jsonEncode(body))),
    200,
    headers: {'content-type': 'application/json'},
  );
}
