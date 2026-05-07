import { useState, useEffect } from "react";
import { View, Text, StyleSheet, TouchableOpacity, Alert } from "react-native";
import Slider from "@react-native-community/slider";
import { BACKEND_URL } from "../constants/Config";

const PRESETS = [
  { label: "30 sec (demo)", value: 30 },
  { label: "5 min", value: 300 },
  { label: "15 min", value: 900 },
  { label: "30 min", value: 1800 },
];

function formatThreshold(sec: number): string {
  if (sec < 60) return `${Math.round(sec)} seconds`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return s > 0 ? `${m} min ${s} sec` : `${m} minutes`;
}

export default function SettingsScreen() {
  const [threshold, setThreshold] = useState(300);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch(`${BACKEND_URL}/threshold`)
      .then((r) => r.json())
      .then((d) => setThreshold(d.threshold_sec))
      .catch(() => {});
  }, []);

  const saveThreshold = async (value: number) => {
    try {
      await fetch(`${BACKEND_URL}/threshold`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threshold_sec: value }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      Alert.alert("Error", "Could not reach backend. Is it running?");
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.sectionLabel}>Alert when cow is down for:</Text>

      <View style={styles.thresholdDisplay}>
        <Text style={styles.thresholdValue}>{formatThreshold(threshold)}</Text>
      </View>

      <Slider
        style={styles.slider}
        minimumValue={10}
        maximumValue={3600}
        step={10}
        value={threshold}
        onValueChange={setThreshold}
        minimumTrackTintColor="#15803d"
        maximumTrackTintColor="#d1fae5"
        thumbTintColor="#15803d"
      />

      <View style={styles.presets}>
        {PRESETS.map((p) => (
          <TouchableOpacity
            key={p.value}
            style={[styles.preset, threshold === p.value && styles.presetActive]}
            onPress={() => setThreshold(p.value)}
          >
            <Text
              style={[styles.presetText, threshold === p.value && styles.presetTextActive]}
            >
              {p.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity
        style={[styles.saveButton, saved && styles.saveButtonSaved]}
        onPress={() => saveThreshold(threshold)}
      >
        <Text style={styles.saveButtonText}>{saved ? "Saved ✓" : "Save Threshold"}</Text>
      </TouchableOpacity>

      <View style={styles.info}>
        <Text style={styles.infoText}>
          A push notification will fire when any cow has been continuously down longer than
          this threshold. The alert resets when the cow stands back up.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0fdf4", padding: 24 },
  sectionLabel: { fontSize: 15, color: "#374151", fontWeight: "600", marginBottom: 16 },
  thresholdDisplay: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 20,
    alignItems: "center",
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#bbf7d0",
  },
  thresholdValue: { fontSize: 28, fontWeight: "800", color: "#15803d" },
  slider: { width: "100%", height: 40, marginBottom: 16 },
  presets: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 28 },
  preset: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#d1fae5",
  },
  presetActive: { backgroundColor: "#15803d", borderColor: "#15803d" },
  presetText: { fontSize: 14, color: "#374151" },
  presetTextActive: { color: "#fff", fontWeight: "600" },
  saveButton: {
    backgroundColor: "#15803d",
    borderRadius: 10,
    padding: 16,
    alignItems: "center",
    marginBottom: 24,
  },
  saveButtonSaved: { backgroundColor: "#16a34a" },
  saveButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  info: {
    backgroundColor: "#f0fdf4",
    borderRadius: 8,
    padding: 14,
    borderWidth: 1,
    borderColor: "#bbf7d0",
  },
  infoText: { fontSize: 13, color: "#4b5563", lineHeight: 20 },
});
