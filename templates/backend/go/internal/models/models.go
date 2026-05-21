package models

import "time"

type User struct {
	ID           string `json:"id"`
	Username     string `json:"username"`
	PasswordHash string `json:"-"`
}

type Todo struct {
	ID          string    `json:"id"`
	UserID      string    `json:"-"`
	Title       string    `json:"title"`
	Description *string   `json:"description"`
	Completed   bool      `json:"completed"`
	CreatedAt   time.Time `json:"created_at"`
}

type AuthRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type RegisterResponse struct {
	ID       string `json:"id"`
	Username string `json:"username"`
}

type LoginResponse struct {
	Token string `json:"token"`
}

type TodoCreate struct {
	Title       string  `json:"title"`
	Description *string `json:"description,omitempty"`
}

type TodoUpdate struct {
	Title       *string `json:"title,omitempty"`
	Description *string `json:"description,omitempty"`
	Completed   *bool   `json:"completed,omitempty"`
}
