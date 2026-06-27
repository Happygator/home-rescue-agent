import 'dart:convert';

import 'package:home_rescue/api/api_client.dart';
import 'package:home_rescue/screens/new_issue_screen.dart';
import 'package:home_rescue/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('a cancelled/denied capture attaches no photo', (tester) async {
    final client = ApiClient(
      baseUrl: 'http://test',
      client: MockClient.streaming((req, body) async {
        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({'case_id': 'case-new123'}))),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );

    await tester.binding.setSurfaceSize(const Size(440, 2200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: NewIssueScreen(client: client, capturePhoto: () async => null),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Add a photo'));
    await tester.pumpAndSettle();

    // Nothing was attached, so the attach affordance stays and no thumbnail appears.
    expect(find.text('Photo attached'), findsNothing);
    expect(find.text('Add a photo'), findsOneWidget);
  });
}
