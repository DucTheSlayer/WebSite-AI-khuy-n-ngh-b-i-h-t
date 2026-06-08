package com.example.musicrecommender.config;

import com.example.musicrecommender.entity.Song;
import com.example.musicrecommender.repository.SongRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

@Component
public class DataInitializer implements CommandLineRunner {
    private static final int EXPECTED_COLUMNS = 21;
    private static final Logger log = LoggerFactory.getLogger(DataInitializer.class);

    private final SongRepository songRepository;
    private final String datasetPath;
    private final int maxRowsToLoad;
    private final int batchSize;

    public DataInitializer(
        SongRepository songRepository,
        @Value("${app.dataset.csv-path:../data/dataset.csv}") String datasetPath,
        @Value("${app.dataset.max-load:0}") int maxRowsToLoad,
        @Value("${app.dataset.batch-size:1000}") int batchSize
    ) {
        this.songRepository = songRepository;
        this.datasetPath = datasetPath;
        this.maxRowsToLoad = maxRowsToLoad;
        this.batchSize = Math.max(batchSize, 1);
    }

    @Override
    public void run(String... args) throws Exception {
        if (songRepository.count() > 0) {
            log.info("Song table already contains data. Skipping CSV import.");
            return;
        }

        Path csvPath = Paths.get(datasetPath).toAbsolutePath().normalize();
        if (!Files.exists(csvPath)) {
            log.warn("Dataset file not found at {}", csvPath);
            return;
        }

        List<Song> batch = new ArrayList<>(batchSize);
        int loaded = 0;

        try (BufferedReader reader = Files.newBufferedReader(csvPath)) {
            String line = reader.readLine(); // skip malformed header from dataset
            while ((line = reader.readLine()) != null) {
                if (maxRowsToLoad > 0 && loaded >= maxRowsToLoad) {
                    break;
                }

                if (line.isBlank()) {
                    continue;
                }

                Song song = toSong(line);
                if (song.getTrackId() == null || song.getTrackId().isBlank()) {
                    continue;
                }

                batch.add(song);
                loaded++;

                if (batch.size() >= batchSize) {
                    songRepository.saveAll(batch);
                    batch.clear();
                }
            }

            if (!batch.isEmpty()) {
                songRepository.saveAll(batch);
            }
        }

        log.info("Imported {} songs from {}", loaded, csvPath);
    }

    private Song toSong(String line) {
        String[] parts = splitCsvLine(line);
        if (parts.length == EXPECTED_COLUMNS + 1 && parts[15].isBlank()) {
            parts = fixMalformedRow(parts);
        }

        if (parts.length != EXPECTED_COLUMNS) {
            return new Song();
        }

        String trackId = parts[1].trim();
        String artists = parts[2].trim();
        String trackName = parts[4].trim();
        String popularity = parts[5].trim();
        String trackGenre = parts[20].trim();

        Song song = new Song();
        song.setTrackId(trackId);
        song.setArtists(artists);
        song.setTrackName(trackName);
        song.setTrackGenre(trackGenre);
        try {
            song.setPopularity(Integer.parseInt(popularity));
        } catch (NumberFormatException ignored) {
            song.setPopularity(0);
        }
        return song;
    }

    private String[] fixMalformedRow(String[] rawParts) {
        List<String> fixedParts = new ArrayList<>();
        for (int i = 0; i < rawParts.length; i++) {
            if (i == 15) {
                fixedParts.add(rawParts[16].replace("danceability", ""));
                i = 16;
                continue;
            }
            fixedParts.add(rawParts[i]);
        }
        return fixedParts.toArray(new String[0]);
    }

    private String[] splitCsvLine(String line) {
        List<String> parts = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                inQuotes = !inQuotes;
                cur.append(c);
            } else if (c == ',' && !inQuotes) {
                parts.add(cur.toString());
                cur.setLength(0);
            } else {
                cur.append(c);
            }
        }
        parts.add(cur.toString());
        return parts.toArray(new String[0]);
    }
}
