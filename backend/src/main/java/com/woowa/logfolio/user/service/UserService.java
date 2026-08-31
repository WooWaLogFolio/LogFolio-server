package com.woowa.logfolio.user.service;

import com.woowa.logfolio.user.dto.UserCreateRequest;
import com.woowa.logfolio.user.dto.UserResponse;
import com.woowa.logfolio.user.dto.UserUpdateRequest;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    @Transactional
    public UserResponse create(UserCreateRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 사용 중인 이메일입니다.");
        }
        User user = new User(request.email(), request.name(), request.passwordHash());
        return UserResponse.from(userRepository.save(user));
    }

    public UserResponse get(UUID id) {
        return UserResponse.from(findActiveUser(id));
    }

    @Transactional
    public UserResponse update(UUID id, UserUpdateRequest request) {
        User user = findActiveUser(id);
        user.update(request.name(), request.status(), request.onboardingCompletedAt());
        return UserResponse.from(user);
    }

    @Transactional
    public void delete(UUID id) {
        findActiveUser(id).withdraw();
    }

    public User findActiveUser(UUID id) {
        return userRepository.findByIdAndDeletedAtIsNull(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다."));
    }
}
