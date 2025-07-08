"""Pydantic models for floodr API"""

import json as json_module
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class Request(BaseModel):
    """HTTP request model with validation"""

    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] = Field(
        default="GET", description="HTTP method"
    )
    url: Union[HttpUrl, str] = Field(description="URL to request")
    headers: Optional[dict[str, str]] = Field(default=None, description="HTTP headers")
    params: Optional[dict[str, Union[str, list[str]]]] = Field(
        default=None, description="URL query parameters"
    )
    json_data: Optional[Any] = Field(
        default=None, description="JSON body (will be serialized)", alias="json"
    )
    data: Optional[Union[str, bytes, dict[str, Any]]] = Field(
        default=None, description="Form data or raw body"
    )
    timeout: Optional[float] = Field(
        default=None, description="Request timeout in seconds"
    )

    @field_validator("json_data")
    @classmethod
    def validate_json(cls, v: Any) -> Any:
        """Ensure json is serializable"""
        if v is not None:
            try:
                json_module.dumps(v)
            except (TypeError, ValueError) as e:
                raise ValueError(f"JSON must be serializable: {e}") from e
        return v

    @field_validator("method")
    @classmethod
    def uppercase_method(cls, v: str) -> str:
        """Ensure method is uppercase"""
        return v.upper()

    def to_rust_request(self) -> dict[str, Any]:
        """Convert to format expected by Rust"""
        rust_req: dict[str, Any] = {
            "url": str(self.url),
            "method": self.method,
        }

        if self.headers:
            rust_req["headers"] = self.headers

        if self.params:
            rust_req["params"] = self.params

        if self.json_data is not None:
            rust_req["json"] = self.json_data

        if self.data is not None:
            if isinstance(self.data, dict):
                rust_req["data"] = self.data
            elif isinstance(self.data, bytes):
                rust_req["body"] = self.data
            else:
                rust_req["body"] = str(self.data).encode()

        if self.timeout is not None:
            rust_req["timeout"] = self.timeout

        return rust_req

    model_config = ConfigDict(populate_by_name=True)  # Allow using 'json' as field name


class Response(BaseModel):
    """HTTP response model"""

    status_code: int = Field(description="HTTP status code")
    headers: dict[str, str] = Field(description="Response headers")
    content: bytes = Field(description="Raw response body")
    elapsed: float = Field(description="Time taken for the request in seconds")
    url: str = Field(description="Final URL after redirects")
    error: Optional[str] = Field(
        default=None, description="Error message if request failed"
    )

    @property
    def text(self) -> str:
        """Get response body as text"""
        return self.content.decode("utf-8", errors="replace")

    @property
    def ok(self) -> bool:
        """Check if response was successful (2xx status)"""
        return 200 <= self.status_code < 300

    def json_data(self) -> Any:
        """Parse response body as JSON"""
        return json_module.loads(self.text)

    def raise_for_status(self) -> None:
        """Raise an exception for 4xx/5xx status codes or network errors"""
        if self.error:
            raise Exception(f"Request failed: {self.error}")
        if not self.ok:
            raise Exception(f"HTTP {self.status_code} Error for url: {self.url}")

    model_config = ConfigDict(arbitrary_types_allowed=True)
