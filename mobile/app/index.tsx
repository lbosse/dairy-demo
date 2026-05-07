import { useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import { useRouter } from "expo-router";
import { useCowStates, CowState } from "../hooks/useCowStates";

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}m ${s}s`;
}

function CowCard({ cowId, state }: { cowId: string; state: CowState }) {
  const isDown = state.posture === "DOWN";
  return (
    <View style={[styles.card, isDown ? styles.cardDown : styles.cardStanding]}>
      <View style={styles.cardHeader}>
        <Text style={styles.cowId}>Cow #{cowId}</Text>
        <View style={[styles.badge, isDown ? styles.badgeDown : styles.badgeStanding]}>
          <Text style={styles.badgeText}>{state.posture}</Text>
        </View>
      </View>
      {isDown && (
        <Text style={styles.downDuration}>
          Down for {formatDuration(state.down_duration_sec)}
          {state.alerted ? "  · Alert sent" : ""}
        </Text>
      )}
    </View>
  );
}

export default function HomeScreen() {
  const { states, lastUpdated } = useCowStates(2000);
  const router = useRouter();

  const entries = Object.entries(states).sort(([a], [b]) => Number(a) - Number(b));
  const downCount = entries.filter(([, s]) => s.posture === "DOWN").length;

  const renderItem = useCallback(
    ({ item }: { item: [string, CowState] }) => (
      <CowCard cowId={item[0]} state={item[1]} />
    ),
    []
  );

  return (
    <View style={styles.container}>
      <View style={styles.summary}>
        <Text style={styles.summaryText}>
          {entries.length} cows tracked · {downCount} down
        </Text>
        {lastUpdated && (
          <Text style={styles.lastUpdated}>
            Updated {lastUpdated.toLocaleTimeString()}
          </Text>
        )}
      </View>

      {entries.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>No cows detected yet.</Text>
          <Text style={styles.emptySubtext}>
            Run the CV script to start processing video.
          </Text>
        </View>
      ) : (
        <FlatList
          data={entries}
          keyExtractor={([id]) => id}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
        />
      )}

      <TouchableOpacity
        style={styles.settingsButton}
        onPress={() => router.push("/settings")}
      >
        <Text style={styles.settingsButtonText}>Alert Settings</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0fdf4" },
  summary: {
    backgroundColor: "#15803d",
    padding: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  summaryText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  lastUpdated: { color: "#bbf7d0", fontSize: 12 },
  list: { padding: 12, gap: 10 },
  card: {
    borderRadius: 10,
    padding: 14,
    borderLeftWidth: 5,
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  cardStanding: { backgroundColor: "#fff", borderLeftColor: "#22c55e" },
  cardDown: { backgroundColor: "#fff7f7", borderLeftColor: "#ef4444" },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  cowId: { fontSize: 17, fontWeight: "700", color: "#1c1c1e" },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  badgeStanding: { backgroundColor: "#dcfce7" },
  badgeDown: { backgroundColor: "#fee2e2" },
  badgeText: { fontSize: 13, fontWeight: "600" },
  downDuration: { marginTop: 6, fontSize: 14, color: "#dc2626" },
  empty: { flex: 1, justifyContent: "center", alignItems: "center", padding: 40 },
  emptyText: { fontSize: 18, fontWeight: "600", color: "#374151", marginBottom: 8 },
  emptySubtext: { fontSize: 14, color: "#6b7280", textAlign: "center" },
  settingsButton: {
    margin: 16,
    backgroundColor: "#15803d",
    borderRadius: 10,
    padding: 16,
    alignItems: "center",
  },
  settingsButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
