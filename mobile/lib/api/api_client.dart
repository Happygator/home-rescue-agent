import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../device_id.dart';
import '../models.dart';
import 'sse.dart';

class PlateResult {
  final String? brand, model, errorCode;
  PlateResult({this.brand, this.model, this.errorCode});
  factory PlateResult.fromJson(Map<String, dynamic> j) =>
      PlateResult(brand: j['brand'] as String?, model: j['model'] as String?, errorCode: j['error_code'] as String?);
}

class EscalateResult {
  final String draftedEmail;
  final List<InspectionShot> inspectionGuide;
  final List<EscalationStep> escalationSteps;
  final Packet packet;
  EscalateResult({required this.draftedEmail, required this.inspectionGuide, required this.escalationSteps, required this.packet});
  factory EscalateResult.fromJson(Map<String, dynamic> j) => EscalateResult(
        draftedEmail: j['drafted_email'] as String,
        inspectionGuide: (j['inspection_guide'] as List).map((e) => InspectionShot.fromJson(e as Map<String, dynamic>)).toList(),
        escalationSteps: ((j['escalation_steps'] as List?) ?? const []).map((e) => EscalationStep.fromJson(e as Map<String, dynamic>)).toList(),
        packet: Packet.fromJson(j['packet'] as Map<String, dynamic>),
      );
}

class ApiException implements Exception {
  final int statusCode; final String message;
  ApiException(this.statusCode, this.message);
  @override String toString() => 'ApiException($statusCode): $message';
}

class ApiClient {
  final String baseUrl;
  final http.Client _client;
  ApiClient({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? AppConfig.baseUrl,
        _client = client ?? http.Client();

  Uri _u(String path, [Map<String, String>? q]) => Uri.parse('$baseUrl$path').replace(queryParameters: q);

  // Every request carries the anonymous per-device user id so the backend can
  // scope issues to this device without any login. [extra] merges in per-call
  // headers (e.g. Content-Type) and wins on key collisions.
  Map<String, String> _headers([Map<String, String>? extra]) => {
        'X-User-Id': DeviceId.value,
        if (extra != null) ...extra,
      };

  Map<String, dynamic> _decodeObj(http.Response r) {
    if (r.statusCode >= 400) throw ApiException(r.statusCode, utf8.decode(r.bodyBytes));
    return jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
  }

  List<dynamic> _decodeList(http.Response r) {
    if (r.statusCode >= 400) throw ApiException(r.statusCode, utf8.decode(r.bodyBytes));
    return jsonDecode(utf8.decode(r.bodyBytes)) as List<dynamic>;
  }

  Future<List<IssueSummary>> listIssues({String status = 'open'}) async {
    final r = await _client.get(_u('/api/issues', {'status': status}), headers: _headers());
    return _decodeList(r).map((e) => IssueSummary.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<IssueDetail> getIssue(String caseId) async =>
      IssueDetail.fromJson(_decodeObj(await _client.get(_u('/api/issues/$caseId'), headers: _headers())));

  /// Fully-qualified URL for an uploaded media file, for rendering inline (e.g. in a chat bubble).
  String mediaUrl(String caseId, String ref) => '$baseUrl/api/issues/$caseId/media/$ref';

  Future<String> createIssue({String? appliance, String? brand, String? modelNumber, String? symptom, String? errorCode}) async {
    final r = await _client.post(_u('/api/issues'),
        headers: _headers({'Content-Type': 'application/json'}),
        body: jsonEncode({
          'user_id': DeviceId.value,
          if (appliance != null) 'appliance': appliance,
          if (brand != null) 'brand': brand,
          if (modelNumber != null) 'model_number': modelNumber,
          if (symptom != null) 'symptom': symptom,
          if (errorCode != null) 'error_code': errorCode,
        }));
    return _decodeObj(r)['case_id'] as String;
  }

  /// Patch intake fields after the camera-first case is created. `messages` (each {role, text})
  /// are appended to the persisted transcript. Returns the updated IssueDetail.
  Future<IssueDetail> updateIssue(
    String caseId, {
    String? symptomText,
    String? appliance,
    String? brand,
    String? modelNumber,
    String? errorCode,
    List<Map<String, dynamic>>? messages,
  }) async {
    final r = await _client.post(_u('/api/issues/$caseId'),
        headers: _headers({'Content-Type': 'application/json'}),
        body: jsonEncode({
          if (symptomText != null) 'symptom_text': symptomText,
          if (appliance != null) 'appliance': appliance,
          if (brand != null) 'brand': brand,
          if (modelNumber != null) 'model_number': modelNumber,
          if (errorCode != null) 'error_code': errorCode,
          if (messages != null) 'messages': messages,
        }));
    return IssueDetail.fromJson(_decodeObj(r));
  }

  /// Permanently delete a case. Throws ApiException on a non-2xx response.
  Future<void> deleteIssue(String caseId) async {
    final r = await _client.delete(_u('/api/issues/$caseId'), headers: _headers());
    if (r.statusCode >= 400) throw ApiException(r.statusCode, utf8.decode(r.bodyBytes));
  }

  Future<String> uploadMedia(String caseId, List<int> bytes, {required String filename, String kind = 'symptom', String mime = 'application/octet-stream'}) async {
    final req = http.MultipartRequest('POST', _u('/api/issues/$caseId/media'))
      ..headers.addAll(_headers())
      ..fields['kind'] = kind
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final streamed = await _client.send(req);
    final r = await http.Response.fromStream(streamed);
    return _decodeObj(r)['ref'] as String;
  }

  Future<PlateResult> readPlate(String caseId, {String? mediaRef}) async {
    final r = await _client.post(_u('/api/issues/$caseId/plate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({if (mediaRef != null) 'media_ref': mediaRef}));
    return PlateResult.fromJson(_decodeObj(r));
  }

  Future<EscalateResult> escalate(String caseId) async =>
      EscalateResult.fromJson(_decodeObj(await _client.post(_u('/api/issues/$caseId/escalate'), headers: _headers())));

  Future<String> resolve(String caseId) async =>
      _decodeObj(await _client.post(_u('/api/issues/$caseId/resolve'), headers: _headers()))['status'] as String;

  /// Stream agent reply tokens over SSE. Yields each SseEvent as it arrives.
  /// When [mediaRef] is set, the attached photo is handed to the agent for this turn.
  Stream<SseEvent> streamMessage(String caseId, String text, {String? mediaRef}) {
    final req = http.Request('POST', _u('/api/issues/$caseId/message'))
      ..headers.addAll(_headers({'Content-Type': 'application/json'}))
      ..body = jsonEncode({'text': text, if (mediaRef != null) 'media_ref': mediaRef});
    return _streamSse(req);
  }

  /// Auto-kickoff: stream the agent's first diagnosis turn for a freshly created case.
  Stream<SseEvent> streamStart(String caseId) {
    final req = http.Request('POST', _u('/api/issues/$caseId/start'))
      ..headers.addAll(_headers({'Content-Type': 'application/json'}))
      ..body = '{}';
    return _streamSse(req);
  }

  Stream<SseEvent> _streamSse(http.Request req) async* {
    final streamed = await _client.send(req);
    if (streamed.statusCode >= 400) {
      throw ApiException(streamed.statusCode, 'stream failed (${req.url.path})');
    }
    final lines = streamed.stream.transform(utf8.decoder).transform(const LineSplitter());
    await for (final line in lines) {
      final trimmed = line.trimRight();
      if (trimmed.startsWith('data:')) {
        final payload = trimmed.substring(5).trim();
        if (payload.isEmpty) continue;
        yield SseEvent.fromJson(jsonDecode(payload) as Map<String, dynamic>);
      }
    }
  }

  void close() => _client.close();
}
