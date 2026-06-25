/// Render an ISO-8601 timestamp as a compact "updated" label: "just now", "5m ago",
/// "2h ago", "3d ago". Falls back to the raw string on parse failure.
String relativeTime(String iso) {
  DateTime t;
  try {
    t = DateTime.parse(iso).toUtc();
  } catch (_) {
    return iso;
  }
  final now = DateTime.now().toUtc();
  final d = now.difference(t);
  if (d.inMinutes < 1) return 'just now';
  if (d.inMinutes < 60) return '${d.inMinutes}m ago';
  if (d.inHours < 24) return '${d.inHours}h ago';
  return '${d.inDays}d ago';
}
