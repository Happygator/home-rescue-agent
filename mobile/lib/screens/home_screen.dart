import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/app_header.dart';
import '../widgets/issue_card.dart';
import 'new_issue_screen.dart';
import 'issue_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  final ApiClient? client;
  const HomeScreen({super.key, this.client});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final ApiClient _api = widget.client ?? ApiClient();
  List<IssueSummary> _open = [];
  List<IssueSummary> _resolved = [];
  bool _loading = true;
  String? _error;
  bool _showResolved = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final open = await _api.listIssues(status: 'open');
      final resolved = await _api.listIssues(status: 'resolved');
      if (!mounted) return;
      setState(() { _open = open; _resolved = resolved; _loading = false; _error = null; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _loading = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    final list = _showResolved ? _resolved : _open;
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Column(
        children: [
          const AppHeader(title: 'Appliance Fixer', homeBrand: true, trailing: AccountAvatar()),
          Expanded(child: _buildBody(list)),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        shape: const CircleBorder(),
        onPressed: () async {
          await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const NewIssueScreen()));
          _load();
        },
        child: const Icon(Icons.add, color: Colors.white, size: 30),
      ),
    );
  }

  Widget _buildBody(List<IssueSummary> list) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text('Could not load issues.\n$_error', textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted))));
    }
    final dot = String.fromCharCode(0x00B7);
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 18, 16, 24),
        children: [
          Text(_showResolved ? 'Resolved Issues' : 'Open Issues',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.textTitle)),
          const SizedBox(height: 4),
          Text('${list.length} ${_showResolved ? "resolved" : "unresolved"} $dot most recent first',
              style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
          const SizedBox(height: 16),
          ...list.map((i) => IssueCard(
                issue: i,
                onTap: () async {
                  await Navigator.of(context).push(MaterialPageRoute(builder: (_) => IssueDetailScreen(caseId: i.caseId)));
                  _load();
                },
              )),
          const SizedBox(height: 8),
          _footer(dot),
        ],
      ),
    );
  }

  Widget _footer(String dot) {
    final count = _showResolved ? _open.length : _resolved.length;
    final label = _showResolved ? 'View open issues' : 'View resolved ($count)';
    final prefix = _showResolved ? 'Showing resolved $dot ' : 'Showing open issues $dot ';
    // A Wrap of plain Text + a tappable link keeps the line testable (find.text) while
    // rendering identically to the single-line mockup footer.
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text(prefix, style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
          GestureDetector(
            onTap: () => setState(() => _showResolved = !_showResolved),
            child: Text(label, style: const TextStyle(fontSize: 13, color: AppColors.primary, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}
