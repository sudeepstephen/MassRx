import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ViewAssetsHtmlStyle extends StatefulWidget {
  const ViewAssetsHtmlStyle({super.key});

  @override
  State<ViewAssetsHtmlStyle> createState() => _ViewAssetsHtmlStyleState();
}

class _ViewAssetsHtmlStyleState extends State<ViewAssetsHtmlStyle> {
  List<dynamic> assets = [];
  bool loading = true;
  String? token;

  Future<void> fetchAssets() async {
    final prefs = await SharedPreferences.getInstance();
    token = prefs.getString('token');

    if (token == null) {
      Navigator.pushReplacementNamed(context, '/');
      return;
    }

    final res = await http.get(
      Uri.parse('http://localhost:8888/api/assets'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (res.statusCode == 200) {
      final data = jsonDecode(res.body);
      setState(() {
        assets = data['assets'] ?? [];
        loading = false;
      });
    } else {
      print('Asset fetch error: ${res.body}');
      setState(() => loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    fetchAssets();
  }

  TableRow buildAssetRow(Map<String, dynamic> asset) {
    return TableRow(
      children: [
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Text(asset['tag_number'] ?? 'N/A'),
        ),
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Text(asset['description'] ?? ''),
        ),
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Text(asset['type_desc'] ?? ''),
        ),
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Text(asset['facility_id'] ?? ''),
        ),
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Row(
            children: [
              TextButton(onPressed: () {}, child: const Text('Details')),
              TextButton(onPressed: () {}, child: const Text('Edit')),
              TextButton(onPressed: () {}, child: const Text('Delete')),
              TextButton(onPressed: () {}, child: const Text('Work Order')),
            ],
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xfff4f4f4),
      appBar: AppBar(title: const Text('View Assets')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: loading
            ? const Center(child: CircularProgressIndicator())
            : SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Table(
                  defaultColumnWidth: const IntrinsicColumnWidth(),
                  border: TableBorder.all(color: Colors.grey),
                  children: [
                    const TableRow(
                      decoration: BoxDecoration(color: Colors.blue),
                      children: [
                        Padding(
                          padding: EdgeInsets.all(8.0),
                          child: Text(
                            'Tag Number',
                            style: TextStyle(color: Colors.white),
                          ),
                        ),
                        Padding(
                          padding: EdgeInsets.all(8.0),
                          child: Text(
                            'Description',
                            style: TextStyle(color: Colors.white),
                          ),
                        ),
                        Padding(
                          padding: EdgeInsets.all(8.0),
                          child: Text(
                            'Type',
                            style: TextStyle(color: Colors.white),
                          ),
                        ),
                        Padding(
                          padding: EdgeInsets.all(8.0),
                          child: Text(
                            'Facility ID',
                            style: TextStyle(color: Colors.white),
                          ),
                        ),
                        Padding(
                          padding: EdgeInsets.all(8.0),
                          child: Text(
                            'Actions',
                            style: TextStyle(color: Colors.white),
                          ),
                        ),
                      ],
                    ),
                    ...assets.map((a) => buildAssetRow(a)).toList(),
                  ],
                ),
              ),
      ),
    );
  }
}
