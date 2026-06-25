class Diagnosis {
  final String hypothesis;
  final String confidence;

  Diagnosis({required this.hypothesis, required this.confidence});

  factory Diagnosis.fromJson(Map<String, dynamic> j) => Diagnosis(
        hypothesis: j['hypothesis'] as String,
        confidence: j['confidence'] as String,
      );
}

class Step {
  final int stepId;
  final String instruction;
  final String outcome;
  final String? userResult;

  Step({
    required this.stepId,
    required this.instruction,
    required this.outcome,
    this.userResult,
  });

  factory Step.fromJson(Map<String, dynamic> j) => Step(
        stepId: j['step_id'] as int,
        instruction: j['instruction'] as String,
        outcome: j['outcome'] as String,
        userResult: j['user_result'] as String?,
      );

  bool get isDone =>
      outcome == 'resolved' || outcome == 'not_resolved' || outcome == 'skipped';
  bool get isPending => !isDone;
}

class MediaRef {
  final String kind;
  final String ref;
  final String mime;
  final String? takenAt;

  MediaRef({
    required this.kind,
    required this.ref,
    required this.mime,
    this.takenAt,
  });

  factory MediaRef.fromJson(Map<String, dynamic> j) => MediaRef(
        kind: j['kind'] as String,
        ref: j['ref'] as String,
        mime: j['mime'] as String,
        takenAt: j['taken_at'] as String?,
      );
}

class InspectionShot {
  final int shotNo;
  final String whatToFilm;
  final String where;
  final String narration;

  InspectionShot({
    required this.shotNo,
    required this.whatToFilm,
    required this.where,
    required this.narration,
  });

  factory InspectionShot.fromJson(Map<String, dynamic> j) => InspectionShot(
        shotNo: j['shot_no'] as int,
        whatToFilm: j['what_to_film'] as String,
        where: j['where'] as String,
        narration: j['narration'] as String,
      );
}

class Packet {
  final String summary;
  final String? model;
  final String? errorCode;
  final int stepsTried;
  final String? videoRef;
  final int shotsCaptured;
  final int shotsTotal;
  final String? warrantyStatus;

  Packet({
    required this.summary,
    this.model,
    this.errorCode,
    required this.stepsTried,
    this.videoRef,
    required this.shotsCaptured,
    required this.shotsTotal,
    this.warrantyStatus,
  });

  factory Packet.fromJson(Map<String, dynamic> j) => Packet(
        summary: j['summary'] as String,
        model: j['model'] as String?,
        errorCode: j['error_code'] as String?,
        stepsTried: j['steps_tried'] as int,
        videoRef: j['video_ref'] as String?,
        shotsCaptured: j['shots_captured'] as int,
        shotsTotal: j['shots_total'] as int,
        warrantyStatus: j['warranty_status'] as String?,
      );
}

class Escalation {
  final String recipient;
  final String draftedEmail;
  final List<InspectionShot> inspectionGuide;
  final Packet? packet;
  final bool sent;

  Escalation({
    required this.recipient,
    required this.draftedEmail,
    required this.inspectionGuide,
    this.packet,
    required this.sent,
  });

  factory Escalation.fromJson(Map<String, dynamic> j) => Escalation(
        recipient: j['recipient'] as String,
        draftedEmail: j['drafted_email'] as String,
        inspectionGuide: (j['inspection_guide'] as List)
            .map((e) => InspectionShot.fromJson(e as Map<String, dynamic>))
            .toList(),
        packet: j['packet'] == null
            ? null
            : Packet.fromJson(j['packet'] as Map<String, dynamic>),
        sent: j['sent'] as bool,
      );
}

class IssueSummary {
  final String caseId;
  final String title;
  final String? brand;
  final String? appliance;
  final String? modelNumber;
  final String status;
  final String symptom;
  final String nextStep;
  final String updatedAt;

  IssueSummary({
    required this.caseId,
    required this.title,
    this.brand,
    this.appliance,
    this.modelNumber,
    required this.status,
    required this.symptom,
    required this.nextStep,
    required this.updatedAt,
  });

  factory IssueSummary.fromJson(Map<String, dynamic> j) => IssueSummary(
        caseId: j['case_id'] as String,
        title: j['title'] as String,
        brand: j['brand'] as String?,
        appliance: j['appliance'] as String?,
        modelNumber: j['model_number'] as String?,
        status: j['status'] as String,
        symptom: j['symptom'] as String,
        nextStep: j['next_step'] as String,
        updatedAt: j['updated_at'] as String,
      );

  String get displayTitle => _displayTitle(brand, appliance, title);

  Map<String, dynamic> toJson() => {
        'case_id': caseId,
        'title': title,
        'brand': brand,
        'appliance': appliance,
        'model_number': modelNumber,
        'status': status,
        'symptom': symptom,
        'next_step': nextStep,
        'updated_at': updatedAt,
      };
}

class IssueDetail {
  final String caseId;
  final String title;
  final String? brand;
  final String? appliance;
  final String? modelNumber;
  final String status;
  final String symptom;
  final String? errorCode;
  final Diagnosis? diagnosis;
  final List<Step> steps;
  final String nextStep;
  final List<MediaRef> media;
  final Escalation? escalation;
  final String createdAt;
  final String updatedAt;

  IssueDetail({
    required this.caseId,
    required this.title,
    this.brand,
    this.appliance,
    this.modelNumber,
    required this.status,
    required this.symptom,
    this.errorCode,
    this.diagnosis,
    required this.steps,
    required this.nextStep,
    required this.media,
    this.escalation,
    required this.createdAt,
    required this.updatedAt,
  });

  factory IssueDetail.fromJson(Map<String, dynamic> j) => IssueDetail(
        caseId: j['case_id'] as String,
        title: j['title'] as String,
        brand: j['brand'] as String?,
        appliance: j['appliance'] as String?,
        modelNumber: j['model_number'] as String?,
        status: j['status'] as String,
        symptom: j['symptom'] as String,
        errorCode: j['error_code'] as String?,
        diagnosis: j['diagnosis'] == null
            ? null
            : Diagnosis.fromJson(j['diagnosis'] as Map<String, dynamic>),
        steps: (j['steps'] as List)
            .map((e) => Step.fromJson(e as Map<String, dynamic>))
            .toList(),
        nextStep: j['next_step'] as String,
        media: (j['media'] as List)
            .map((e) => MediaRef.fromJson(e as Map<String, dynamic>))
            .toList(),
        escalation: j['escalation'] == null
            ? null
            : Escalation.fromJson(j['escalation'] as Map<String, dynamic>),
        createdAt: j['created_at'] as String,
        updatedAt: j['updated_at'] as String,
      );

  String get displayTitle => _displayTitle(brand, appliance, title);

  Map<String, dynamic> toJson() => {
        'case_id': caseId,
        'title': title,
        'brand': brand,
        'appliance': appliance,
        'model_number': modelNumber,
        'status': status,
        'symptom': symptom,
        'error_code': errorCode,
        'diagnosis': diagnosis == null
            ? null
            : {
                'hypothesis': diagnosis!.hypothesis,
                'confidence': diagnosis!.confidence,
              },
        'steps': steps
            .map((e) => {
                  'step_id': e.stepId,
                  'instruction': e.instruction,
                  'outcome': e.outcome,
                  'user_result': e.userResult,
                })
            .toList(),
        'next_step': nextStep,
        'media': media
            .map((e) => {
                  'kind': e.kind,
                  'ref': e.ref,
                  'mime': e.mime,
                  'taken_at': e.takenAt,
                })
            .toList(),
        'escalation': escalation == null
            ? null
            : {
                'recipient': escalation!.recipient,
                'drafted_email': escalation!.draftedEmail,
                'inspection_guide': escalation!.inspectionGuide
                    .map((e) => {
                          'shot_no': e.shotNo,
                          'what_to_film': e.whatToFilm,
                          'where': e.where,
                          'narration': e.narration,
                        })
                    .toList(),
                'packet': escalation!.packet == null
                    ? null
                    : {
                        'summary': escalation!.packet!.summary,
                        'model': escalation!.packet!.model,
                        'error_code': escalation!.packet!.errorCode,
                        'steps_tried': escalation!.packet!.stepsTried,
                        'video_ref': escalation!.packet!.videoRef,
                        'shots_captured': escalation!.packet!.shotsCaptured,
                        'shots_total': escalation!.packet!.shotsTotal,
                        'warranty_status': escalation!.packet!.warrantyStatus,
                      },
                'sent': escalation!.sent,
              },
        'created_at': createdAt,
        'updated_at': updatedAt,
      };
}

String _displayTitle(String? brand, String? appliance, String title) {
  if (brand != null && appliance != null) {
    return '$brand ${String.fromCharCode(0x00B7)} $appliance';
  }
  return title;
}
