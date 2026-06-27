import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../nav.dart';
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

class _HomeScreenState extends State<HomeScreen> with RouteAware {
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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final route = ModalRoute.of(context);
    if (route is PageRoute) routeObserver.subscribe(this, route);
  }

  @override
  void dispose() {
    routeObserver.unsubscribe(this);
    super.dispose();
  }

  // Fires when a route pushed above Home is popped and Home becomes visible again.
  // Covers the new-issue -> chat (pushReplacement) flow, where Home's own push
  // future resolves early and so cannot trigger a refresh on return.
  @override
  void didPopNext() => _load();

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

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _editIssue(IssueSummary issue) async {
    final result = await showDialog<EditIssueResult>(
      context: context,
      builder: (_) => EditIssueDialog(issue: issue),
    );
    if (result == null) return;
    try {
      await _api.updateIssue(
        issue.caseId,
        appliance: result.appliance,
        brand: result.brand,
        modelNumber: result.modelNumber,
        symptomText: result.symptom,
        errorCode: result.errorCode,
      );
      await _load();
      _showSnack('Ticket updated.');
    } catch (e) {
      _showSnack('Could not save changes: $e');
    }
  }

  Future<void> _deleteIssue(IssueSummary issue) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete ticket?'),
        content: Text(
          'This permanently removes "${issue.displayTitle}" and all of its '
          'history. This cannot be undone.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: const Color(0xFFB91C1C)),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _api.deleteIssue(issue.caseId);
      await _load();
    } catch (e) {
      _showSnack('Could not delete ticket: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final list = _showResolved ? _resolved : _open;
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Column(
        children: [
          const AppHeader(title: 'HomeRescue', homeBrand: true, trailing: AccountAvatar()),
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
                onEdit: () => _editIssue(i),
                onDelete: () => _deleteIssue(i),
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

/// Values returned by [EditIssueDialog]. Empty strings are intentional (a cleared
/// field) and are sent to the API as-is so the user can blank out a value.
class EditIssueResult {
  final String appliance;
  final String brand;
  final String modelNumber;
  final String symptom;
  final String errorCode;
  const EditIssueResult({
    required this.appliance,
    required this.brand,
    required this.modelNumber,
    required this.symptom,
    required this.errorCode,
  });
}

/// Edit the exact parameters of a ticket. Returns an [EditIssueResult] on Save,
/// or null when dismissed.
class EditIssueDialog extends StatefulWidget {
  final IssueSummary issue;
  const EditIssueDialog({super.key, required this.issue});

  @override
  State<EditIssueDialog> createState() => _EditIssueDialogState();
}

class _EditIssueDialogState extends State<EditIssueDialog> {
  late final TextEditingController _appliance =
      TextEditingController(text: widget.issue.appliance ?? '');
  late final TextEditingController _brand =
      TextEditingController(text: widget.issue.brand ?? '');
  late final TextEditingController _model =
      TextEditingController(text: widget.issue.modelNumber ?? '');
  late final TextEditingController _symptom =
      TextEditingController(text: widget.issue.symptom);
  final TextEditingController _errorCode = TextEditingController();

  @override
  void dispose() {
    _appliance.dispose();
    _brand.dispose();
    _model.dispose();
    _symptom.dispose();
    _errorCode.dispose();
    super.dispose();
  }

  void _save() {
    Navigator.pop(
      context,
      EditIssueResult(
        appliance: _appliance.text.trim(),
        brand: _brand.text.trim(),
        modelNumber: _model.text.trim(),
        symptom: _symptom.text.trim(),
        errorCode: _errorCode.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: AppColors.card,
      title: const Text('Edit ticket'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _field(_appliance, 'Appliance', 'e.g. Refrigerator'),
            const SizedBox(height: 12),
            _field(_brand, 'Brand', 'e.g. Samsung'),
            const SizedBox(height: 12),
            _field(_model, 'Model number', 'e.g. RF28R7201'),
            const SizedBox(height: 12),
            _field(_symptom, 'Symptom', 'What is it doing wrong?', maxLines: 3),
            const SizedBox(height: 12),
            _field(_errorCode, 'Error code', 'e.g. 1E (optional)'),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: AppColors.primary, foregroundColor: Colors.white),
          onPressed: _save,
          child: const Text('Save'),
        ),
      ],
    );
  }

  Widget _field(TextEditingController controller, String label, String hint, {int maxLines = 1}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: AppColors.textBody2)),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          minLines: 1,
          maxLines: maxLines,
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(color: AppColors.textFaint),
            isDense: true,
            filled: true,
            fillColor: AppColors.bg,
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: AppColors.divider),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: AppColors.primary),
            ),
          ),
        ),
      ],
    );
  }
}
