# Community Library API

A fictional API for a small community library. Use it to look up books, register members, and lend and return books.

- **Version:** 1.0.0
- **Base URL:** `https://api.example-library.test`

## Endpoints

- [GET /books](#get-books): List books
- [GET /books/{id}](#get-booksid): Get one book
- [POST /members](#post-members): Register a member
- [POST /loans](#post-loans): Lend a book to a member
- [DELETE /loans/{id}](#delete-loansid): Return a book

## GET /books

List books

Returns books in the catalogue. Filters can be combined.

### Parameters

| Name | In | Type | Required | Description |
|---|---|---|---|---|
| author | query | string | no | Only books by this author |
| available | query | boolean | no | true for books not currently on loan |
| limit | query | integer | no | Maximum number of results (default 20) |

### Responses

#### 200: A list of books

```json
[
  {
    "author": "Herman Melville",
    "available": true,
    "id": 7,
    "title": "Moby Dick"
  },
  {
    "author": "James Joyce",
    "available": false,
    "id": 12,
    "title": "Dubliners"
  }
]
```

## GET /books/{id}

Get one book

Returns a single book by its ID, including whether it is available

### Parameters

| Name | In | Type | Required | Description |
|---|---|---|---|---|
| id | path | integer | yes | The book's id |

### Responses

#### 200: Book found

```json
{
  "author": "Herman Melville",
  "available": true,
  "id": 7,
  "title": "Moby Dick"
}
```

#### 404: No book with that id

## POST /members

Register a member

Registers a member by its name and email address

### Parameters

| Name | In | Type | Required | Description |
|---|---|---|---|---|
| name | body | string | yes | Full name |
| email | body | string | yes | Contact email address |

### Responses

#### 201: Member created

```json
{
  "email": "aoife@example.test",
  "id": 301,
  "name": "Aoife Byrne"
}
```

#### 400: Name or email is missing

```json
{
  "error": "email is required"
}
```

## POST /loans

Lend a book to a member

A member can hold at most five books at a time.

### Parameters

| Name | In | Type | Required | Description |
|---|---|---|---|---|
| book_id | body | integer | yes | The book to lend |
| member_id | body | integer | yes | The member borrowing it |

### Responses

#### 201: Loan created

```json
{
  "book_id": 7,
  "due": "2026-11-15",
  "id": 9001,
  "member_id": 301
}
```

#### 404: Book or member not found

#### 409: Book is already on loan

## DELETE /loans/{id}

Return a book

Ends a loan when a member returns a book. The book becomes available to borrow again.

### Parameters

| Name | In | Type | Required | Description |
|---|---|---|---|---|
| id | path | integer | yes | The loan id |

### Responses

#### 204: Book returned

#### 404: No loan with that id
