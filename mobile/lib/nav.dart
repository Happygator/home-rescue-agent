import 'package:flutter/material.dart';

/// App-wide route observer so screens can refresh when they become visible again
/// (e.g. Home re-fetching after returning from the new-issue -> chat flow, which
/// uses pushReplacement and so does not keep Home's push future alive).
final RouteObserver<ModalRoute<void>> routeObserver =
    RouteObserver<ModalRoute<void>>();
