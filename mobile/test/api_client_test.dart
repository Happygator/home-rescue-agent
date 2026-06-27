import 'dart:convert';
import 'dart:io';

import 'package:home_rescue/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const baseUrl = 'http://example.test';

  String fixture(String name) =>
      File('test/fixtures/$name').readAsStringSync();

  http.Response fixtureResponse(String name) =>
      http.Response.bytes(utf8.encode(fixture(name)), 200);

  test('listIssues hits open issues endpoint and parses fixture', () async {
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/api/issues');
        expect(req.url.queryParameters['status'], 'open');
        return fixtureResponse('issues_list.json');
      }),
    );

    final issues = await client.listIssues();

    expect(issues, hasLength(3));
  });

  test('getIssue hits issue path and parses fixture', () async {
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/api/issues/case-7f3a9c21');
        return fixtureResponse('issue_detail_diagnosing.json');
      }),
    );

    final issue = await client.getIssue('case-7f3a9c21');

    expect(issue.caseId, 'case-7f3a9c21');
  });

  test('createIssue posts body and returns case id', () async {
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/api/issues');
        expect(jsonDecode(req.body)['appliance'], 'Refrigerator');
        return fixtureResponse('create_response.json');
      }),
    );

    final caseId = await client.createIssue(appliance: 'Refrigerator');

    expect(caseId, isA<String>());
  });

  test('readPlate returns brand and model', () async {
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/api/issues/case-7f3a9c21/plate');
        return fixtureResponse('plate_response.json');
      }),
    );

    final plate = await client.readPlate('case-7f3a9c21');

    expect(plate.brand, isNotEmpty);
    expect(plate.model, isNotEmpty);
  });

  test('escalate parses guide and packet', () async {
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/api/issues/case-7f3a9c21/escalate');
        return fixtureResponse('escalate_response.json');
      }),
    );

    final result = await client.escalate('case-7f3a9c21');

    expect(result.inspectionGuide, hasLength(4));
    expect(result.packet.shotsTotal, 4);
  });

  test('streamMessage parses SSE events', () async {
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient.streaming((req, bodyStream) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/api/issues/case-7f3a9c21/message');
        return http.StreamedResponse(
          Stream.value(utf8.encode(
            'data: {"type":"token","text":"Hi"}\n\n'
            'data: {"type":"token","text":" there"}\n\n'
            'data: {"type":"done","status":"diagnosing"}\n\n',
          )),
          200,
          headers: {'content-type': 'text/event-stream'},
        );
      }),
    );

    final events = await client.streamMessage('case-7f3a9c21', 'hello').toList();

    expect(events, hasLength(3));
    expect(events[0].type, 'token');
    expect(events[0].text, 'Hi');
    expect(events[1].type, 'token');
    expect(events[1].text, ' there');
    expect(events[2].type, 'done');
    expect(events[2].status, 'diagnosing');
  });

  test('404 throws ApiException', () async {
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient((req) async => http.Response.bytes(
        utf8.encode('not found'),
        404,
      )),
    );

    expect(client.listIssues(), throwsA(isA<ApiException>()));
  });
}
