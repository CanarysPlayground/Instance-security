package io.codecov;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class LoggerExample {
    private static final Logger logger = LoggerFactory.getLogger(LoggerExample.class);

    public void logSensitiveData(String password) {
        logger.info("User password: " + password);  // Unsafe logging
    }
}
