package com.woowa.logfolio.ai;

public class AiServerException extends RuntimeException {
    private final boolean retryable;

    public AiServerException(String message, boolean retryable, Throwable cause) {
        super(message, cause);
        this.retryable = retryable;
    }

    public boolean isRetryable() { return retryable; }
}
