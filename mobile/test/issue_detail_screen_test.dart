import 'dart:convert';
import 'dart:io';

import 'package:appliance_fixer/api/api_client.dart';
import 'package:appliance_fixer/screens/issue_detail_screen.dart';
import 'package:appliance_fixer/theme.dart';
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
}
