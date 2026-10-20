package com.wifiintegrity.inspector.util;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class CsvTable {
    private CsvTable() {}

    public static List<Map<String, String>> parse(String text) throws IOException {
        BufferedReader reader = new BufferedReader(new StringReader(text));
        String headerLine = reader.readLine();
        if (headerLine == null) return new ArrayList<>();
        List<String> headers = parseLine(headerLine);
        List<Map<String, String>> rows = new ArrayList<>();
        String line;
        while ((line = reader.readLine()) != null) {
            if (line.trim().isEmpty()) continue;
            List<String> values = parseLine(line);
            Map<String, String> row = new LinkedHashMap<>();
            for (int i = 0; i < headers.size(); i++) row.put(headers.get(i).trim(), i < values.size() ? values.get(i).trim() : "");
            rows.add(row);
        }
        return rows;
    }

    private static List<String> parseLine(String line) {
        List<String> values = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
            } else if (ch == ',' && !quoted) {
                values.add(current.toString());
                current.setLength(0);
            } else {
                current.append(ch);
            }
        }
        values.add(current.toString());
        return values;
    }
}
