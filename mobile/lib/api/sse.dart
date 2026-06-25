/// A parsed Server-Sent Event from POST /api/issues/{id}/message.
class SseEvent {
  final String type;       // 'token' | 'done'
  final String? text;      // present for token events
  final String? status;    // present for done events
  SseEvent({required this.type, this.text, this.status});
  factory SseEvent.fromJson(Map<String, dynamic> j) =>
      SseEvent(type: j['type'] as String? ?? 'token', text: j['text'] as String?, status: j['status'] as String?);
}
