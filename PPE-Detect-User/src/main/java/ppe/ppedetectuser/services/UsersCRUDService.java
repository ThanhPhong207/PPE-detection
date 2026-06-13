package ppe.ppedetectuser.services;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import ppe.ppedetectuser.entities.DTO.UsersDTO;
import ppe.ppedetectuser.entities.Users;
import ppe.ppedetectuser.entities.response.ResponseData;
import ppe.ppedetectuser.repositories.UsersRepository;

@Service
@RequiredArgsConstructor
public class UsersCRUDService {

    private final UsersRepository usersRepository;

    public ResponseEntity<ResponseData<UsersDTO>> getById(Long id) {
        return usersRepository.findById(id)
                .map(user -> {
                    UsersDTO dto = UsersDTO.builder()
                            .id(user.getId())
                            .email(user.getEmail())
                            .fullName(user.getFullName())
                            .avatarUrl(user.getAvatarUrl())
                            .googleId(user.getGoogleId())
                            .role(user.getRole())
                            .active(user.isActive())
                            .createdAt(user.getCreatedAt())
                            .lastLogin(user.getLastLogin())
                            .build();
                    
                    ResponseData<UsersDTO> response = ResponseData.<UsersDTO>builder()
                            .statusCode(String.valueOf(HttpStatus.OK.value()))
                            .message("User found successfully")
                            .data(dto)
                            .build();
                    return ResponseEntity.ok(response);
                })
                .orElseGet(() -> {
                    ResponseData<UsersDTO> response = ResponseData.<UsersDTO>builder()
                            .statusCode(String.valueOf(HttpStatus.NOT_FOUND.value()))
                            .message("User not found")
                            .build();
                    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(response);
                });
    }
}
