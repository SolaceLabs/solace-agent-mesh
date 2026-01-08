"""
Unit tests for version response DTOs.

Tests the Pydantic models used for version information responses.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.gateway.http_sse.routers.dto.responses.version_responses import (
    ProductInfo,
    VersionResponse,
)


class TestProductInfo:
    """Tests for the ProductInfo DTO."""

    def test_product_info_valid_minimal(self):
        """Test creating a ProductInfo with minimal required fields."""
        product = ProductInfo(
            id="test-product",
            name="Test Product",
            description="A test product",
            version="1.0.0",
        )
        assert product.id == "test-product"
        assert product.name == "Test Product"
        assert product.description == "A test product"
        assert product.version == "1.0.0"
        assert product.dependencies is None

    def test_product_info_with_dependencies(self):
        """Test creating a ProductInfo with dependencies."""
        dependencies = {
            "dep1": "1.0.0",
            "dep2": "2.1.0",
            "dep3": "3.0.0-beta",
        }
        product = ProductInfo(
            id="test-product",
            name="Test Product",
            description="A test product",
            version="1.0.0",
            dependencies=dependencies,
        )
        assert product.dependencies == dependencies
        assert len(product.dependencies) == 3

    def test_product_info_empty_dependencies(self):
        """Test creating a ProductInfo with empty dependencies dict."""
        product = ProductInfo(
            id="test-product",
            name="Test Product",
            description="A test product",
            version="1.0.0",
            dependencies={},
        )
        assert product.dependencies == {}

    def test_product_info_missing_required_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ProductInfo(
                name="Test Product",
                description="A test product",
                version="1.0.0",
                # Missing 'id'
            )
        assert "id" in str(exc_info.value)

    def test_product_info_empty_string_fields(self):
        """Test that empty strings are allowed for text fields."""
        product = ProductInfo(
            id="",
            name="",
            description="",
            version="",
        )
        assert product.id == ""
        assert product.name == ""
        assert product.description == ""
        assert product.version == ""

    def test_product_info_serialization(self):
        """Test that ProductInfo can be serialized to dict."""
        product = ProductInfo(
            id="test-product",
            name="Test Product",
            description="A test product",
            version="1.0.0",
            dependencies={"dep1": "1.0.0"},
        )
        data = product.model_dump()
        assert data["id"] == "test-product"
        assert data["name"] == "Test Product"
        assert data["description"] == "A test product"
        assert data["version"] == "1.0.0"
        assert data["dependencies"] == {"dep1": "1.0.0"}

    def test_product_info_serialization_without_dependencies(self):
        """Test that ProductInfo serialization excludes None dependencies."""
        product = ProductInfo(
            id="test-product",
            name="Test Product",
            description="A test product",
            version="1.0.0",
        )
        data = product.model_dump(exclude_none=True)
        assert "dependencies" not in data

    def test_product_info_deserialization(self):
        """Test that ProductInfo can be deserialized from dict."""
        data = {
            "id": "test-product",
            "name": "Test Product",
            "description": "A test product",
            "version": "1.0.0",
            "dependencies": {"dep1": "1.0.0"},
        }
        product = ProductInfo.model_validate(data)
        assert product.id == "test-product"
        assert product.name == "Test Product"
        assert product.dependencies == {"dep1": "1.0.0"}

    def test_product_info_extra_fields_ignored(self):
        """Test that extra fields are handled according to config."""
        data = {
            "id": "test-product",
            "name": "Test Product",
            "description": "A test product",
            "version": "1.0.0",
            "extra_field": "should be ignored",
        }
        # By default, Pydantic v2 ignores extra fields
        product = ProductInfo.model_validate(data)
        assert not hasattr(product, "extra_field")

    def test_product_info_special_characters_in_strings(self):
        """Test that special characters in strings are preserved."""
        product = ProductInfo(
            id="@org/product-name",
            name="Product™ with ©",
            description="Description with\nnewlines\tand\ttabs",
            version="1.0.0-beta.1+build.123",
        )
        assert product.id == "@org/product-name"
        assert "™" in product.name
        assert "\n" in product.description
        assert "+" in product.version

    def test_product_info_unicode_support(self):
        """Test that unicode characters are supported."""
        product = ProductInfo(
            id="产品",
            name="Продукт",
            description="محصول",
            version="1.0.0",
        )
        assert product.id == "产品"
        assert product.name == "Продукт"
        assert product.description == "محصول"


class TestVersionResponse:
    """Tests for the VersionResponse DTO."""

    def test_version_response_with_single_product(self):
        """Test creating a VersionResponse with a single product."""
        product = ProductInfo(
            id="test-product",
            name="Test Product",
            description="A test product",
            version="1.0.0",
        )
        response = VersionResponse(products=[product])
        assert len(response.products) == 1
        assert response.products[0].id == "test-product"

    def test_version_response_with_multiple_products(self):
        """Test creating a VersionResponse with multiple products."""
        products = [
            ProductInfo(
                id="product-1",
                name="Product 1",
                description="First product",
                version="1.0.0",
            ),
            ProductInfo(
                id="product-2",
                name="Product 2",
                description="Second product",
                version="2.0.0",
                dependencies={"dep1": "1.0.0"},
            ),
            ProductInfo(
                id="product-3",
                name="Product 3",
                description="Third product",
                version="3.0.0",
            ),
        ]
        response = VersionResponse(products=products)
        assert len(response.products) == 3
        assert response.products[0].id == "product-1"
        assert response.products[1].id == "product-2"
        assert response.products[1].dependencies == {"dep1": "1.0.0"}
        assert response.products[2].id == "product-3"

    def test_version_response_empty_products_list(self):
        """Test creating a VersionResponse with empty products list."""
        response = VersionResponse(products=[])
        assert len(response.products) == 0
        assert response.products == []

    def test_version_response_missing_products_field(self):
        """Test that missing products field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            VersionResponse()
        assert "products" in str(exc_info.value)

    def test_version_response_serialization(self):
        """Test that VersionResponse can be serialized to dict."""
        products = [
            ProductInfo(
                id="product-1",
                name="Product 1",
                description="First product",
                version="1.0.0",
            ),
        ]
        response = VersionResponse(products=products)
        data = response.model_dump()
        assert "products" in data
        assert len(data["products"]) == 1
        assert data["products"][0]["id"] == "product-1"

    def test_version_response_deserialization(self):
        """Test that VersionResponse can be deserialized from dict."""
        data = {
            "products": [
                {
                    "id": "product-1",
                    "name": "Product 1",
                    "description": "First product",
                    "version": "1.0.0",
                },
                {
                    "id": "product-2",
                    "name": "Product 2",
                    "description": "Second product",
                    "version": "2.0.0",
                    "dependencies": {"dep1": "1.0.0"},
                },
            ]
        }
        response = VersionResponse.model_validate(data)
        assert len(response.products) == 2
        assert response.products[0].id == "product-1"
        assert response.products[1].dependencies == {"dep1": "1.0.0"}

    def test_version_response_json_schema(self):
        """Test that VersionResponse generates valid JSON schema."""
        schema = VersionResponse.model_json_schema()
        assert "properties" in schema
        assert "products" in schema["properties"]
        assert schema["required"] == ["products"]

    def test_version_response_invalid_product_type(self):
        """Test that invalid product type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            VersionResponse(products=["invalid", "product", "list"])
        assert "products" in str(exc_info.value)

    def test_version_response_round_trip_serialization(self):
        """Test that serialization and deserialization preserve data."""
        original = VersionResponse(
            products=[
                ProductInfo(
                    id="product-1",
                    name="Product 1",
                    description="First product",
                    version="1.0.0",
                    dependencies={"dep1": "1.0.0", "dep2": "2.0.0"},
                ),
            ]
        )
        # Serialize to dict
        data = original.model_dump()
        # Deserialize back
        restored = VersionResponse.model_validate(data)
        # Compare
        assert restored.products[0].id == original.products[0].id
        assert restored.products[0].name == original.products[0].name
        assert restored.products[0].version == original.products[0].version
        assert restored.products[0].dependencies == original.products[0].dependencies

    def test_version_response_json_round_trip(self):
        """Test that JSON serialization and deserialization preserve data."""
        original = VersionResponse(
            products=[
                ProductInfo(
                    id="product-1",
                    name="Product 1",
                    description="First product",
                    version="1.0.0",
                ),
            ]
        )
        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = VersionResponse.model_validate_json(json_str)
        # Compare
        assert restored.products[0].id == original.products[0].id
        assert restored.products[0].name == original.products[0].name

    def test_version_response_with_none_dependencies(self):
        """Test that None dependencies are handled correctly."""
        product = ProductInfo(
            id="product-1",
            name="Product 1",
            description="First product",
            version="1.0.0",
            dependencies=None,
        )
        response = VersionResponse(products=[product])
        data = response.model_dump(exclude_none=True)
        # Dependencies should not be in the serialized data
        assert "dependencies" not in data["products"][0]
