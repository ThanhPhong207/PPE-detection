package ppe.ppedetectuser.config.authentication;

import org.springframework.stereotype.Service;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class TokenBlacklistService {

    private final Map<String, Boolean> blacklistMap = new ConcurrentHashMap<>();
    private final Map<String, String> refreshMap = new ConcurrentHashMap<>();

    public void blacklist(String token, long ttlMillis) {
        blacklistMap.put(token, true);
    }

    public boolean isBlacklisted(String token) {
        return blacklistMap.containsKey(token);
    }

    public void saveRefreshToken(String userId, String refreshToken, long ttlMillis) {
        refreshMap.put(userId, refreshToken);
    }

    public String getRefreshToken(String userId) {
        return refreshMap.get(userId);
    }

    public void deleteRefreshToken(String userId) {
        refreshMap.remove(userId);
    }
}