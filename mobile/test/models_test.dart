import 'dart:convert';
import 'dart:io';

import 'package:appliance_fixer/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  dynamic fixture(String name) =>
      jsonDecode(File('test/fixtures/$name').readAsStringSync());

  test('parses issues list summaries', () {
    final data = fixture('issues_list.json') as List<dynamic>;
    final issues = data
        .map((e) => IssueSummary.fromJson(e as Map<String, dynamic>))
        .toList();

    expect(issues, hasLength(3));
    expect(issues.first.caseId, 'case-7f3a9c21');
    expect(issues.first.status, 'diagnosing');
    expect(
      issues.first.displayTitle,
      'Samsung ${String.fromCharCode(0x00B7)} Refrigerator',
    );
    expect(issues.first.nextStep, isNotEmpty);
  });

  test('parses diagnosing issue detail', () {
    final detail = IssueDetail.fromJson(
      fixture('issue_detail_diagnosing.json') as Map<String, dynamic>,
    );

    expect(detail.steps, hasLength(3));
    expect(detail.steps[0].outcome, 'not_resolved');
    expect(detail.steps[0].isDone, isTrue);
    expect(detail.steps[2].outcome, 'pending');
    expect(detail.steps[2].isPending, isTrue);
    expect(
      detail.diagnosis!.hypothesis.contains('airflow') ||
          detail.diagnosis!.hypothesis.contains('coils'),
      isTrue,
    );
  });

  test('parses escalated issue detail', () {
    final detail = IssueDetail.fromJson(
      fixture('issue_detail_escalated.json') as Map<String, dynamic>,
    );

    expect(detail.escalation, isNotNull);
    expect(detail.escalation!.inspectionGuide, hasLength(4));
    expect(
      detail.escalation!.inspectionGuide[1].whatToFilm,
      'Frame the display panel',
    );
    expect(detail.escalation!.packet!.shotsTotal, 4);
    expect(detail.escalation!.packet!.stepsTried, 3);
  });

  test('create response has case id', () {
    final data = fixture('create_response.json') as Map<String, dynamic>;

    expect(data['case_id'], isA<String>());
  });

  test('summary round trip preserves case id and status', () {
    final data = fixture('issues_list.json') as List<dynamic>;
    final summary = IssueSummary.fromJson(data.first as Map<String, dynamic>);
    final json = summary.toJson();

    expect(json['case_id'], summary.caseId);
    expect(json['status'], summary.status);
  });
}
