using System.Text;
using Microsoft.Data.Sqlite;

namespace LightroomMcp.Saved;

public sealed record CatalogReference(long Sequence, string DocId, bool Current, bool Winning, bool MentionsPhoto);

/// <summary>
/// Read-only check that Lightroom's catalog (Managed Catalog.mcat, SQLite with docs/revs tables) points at a
/// settings file. Revision content is a binary document encoding, so the check is a byte search for the
/// settings file's SHA-256 (and optionally the photo's file name) in revision content.
/// Never opens the live file: it copies the catalog to a temp file first.
/// </summary>
public static class CatalogReader
{
    public static IReadOnlyList<CatalogReference> FindReferences(string catalogDir, string settingsSha256, string? photoName = null, int limit = 10)
    {
        var live = Path.Combine(catalogDir, "Managed Catalog.mcat");
        if (!File.Exists(live))
            throw new FileNotFoundException("Managed Catalog.mcat not found.", live);

        var temp = Path.Combine(Path.GetTempPath(), "lightroom-mcp", $"catalog-{Guid.NewGuid():N}.mcat");
        Directory.CreateDirectory(Path.GetDirectoryName(temp)!);
        try
        {
            using (var src = new FileStream(live, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            using (var dst = File.Create(temp))
                src.CopyTo(dst);
            foreach (var suffix in new[] { "-wal", "-shm" })
                if (File.Exists(live + suffix))
                    using (var s = new FileStream(live + suffix, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                    using (var d = File.Create(temp + suffix))
                        s.CopyTo(d);

            using var conn = new SqliteConnection(new SqliteConnectionStringBuilder
            {
                DataSource = temp,
                Mode = SqliteOpenMode.ReadOnly,
                Pooling = false
            }.ToString());
            conn.Open();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = """
                SELECT r.sequence, d.fullDocId, r.current, (d.winningRevSequence = r.sequence),
                       CASE WHEN $photo IS NULL THEN 0 ELSE instr(r.content, $photo) > 0 END
                FROM revs r JOIN docs d ON d.localDocId = r.localDocId
                WHERE instr(r.content, $hash) > 0
                ORDER BY r.sequence DESC LIMIT $limit
                """;
            cmd.Parameters.AddWithValue("$hash", Encoding.ASCII.GetBytes(settingsSha256.ToLowerInvariant()));
            cmd.Parameters.AddWithValue("$photo", photoName is null ? DBNull.Value : Encoding.UTF8.GetBytes(photoName));
            cmd.Parameters.AddWithValue("$limit", limit);

            var result = new List<CatalogReference>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
                result.Add(new CatalogReference(reader.GetInt64(0), reader.GetString(1),
                    !reader.IsDBNull(2) && reader.GetInt64(2) != 0, !reader.IsDBNull(3) && reader.GetInt64(3) != 0,
                    !reader.IsDBNull(4) && reader.GetInt64(4) != 0));
            return result;
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            foreach (var f in new[] { temp, temp + "-wal", temp + "-shm" })
                try { File.Delete(f); } catch (IOException) { }
        }
    }
}
