
"""
Unit tests for src/solace_agent_mesh/agent/adk/artifacts/s3_artifact_service.py

Tests the S3ArtifactService implementation including:
- Initialization and S3 client setup
- Bucket validation and access checks
- Artifact saving with versioning
- Artifact loading (latest and specific versions)
- Artifact listing and key management
- Artifact deletion
- Version management
- Unicode filename normalization
- User namespace handling
- Error handling and AWS exceptions
"""

import unicodedata
from unittest.mock import Mock, patch
import pytest
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError

from google.genai import types as adk_types
from src.solace_agent_mesh.agent.adk.artifacts.s3_artifact_service import S3ArtifactService


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client"""
    client = Mock()
    client.head_bucket.return_value = {}
    client.put_object.return_value = {'ETag': '"test-etag"'}
    client.get_object.return_value = {
        'Body': Mock(read=Mock(return_value=b"test data")),
        'ContentType': 'text/plain'
    }
    client.delete_object.return_value = {}
    
    # Mock paginator
    paginator = Mock()
    paginator.paginate.return_value = [{'Contents': []}]
    client.get_paginator.return_value = paginator
    
    return client


@pytest.fixture
def sample_artifact():
    """Create a sample artifact for testing"""
    data = b"Hello, World!"
    mime_type = "text/plain"
    return adk_types.Part.from_bytes(data=data, mime_type=mime_type)


@pytest.fixture
def sample_binary_artifact():
    """Create a sample binary artifact for testing"""
    data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    mime_type = "image/png"
    return adk_types.Part.from_bytes(data=data, mime_type=mime_type)


class TestS3ArtifactServiceInit:
    """Tests for S3ArtifactService initialization"""

    def test_init_with_valid_bucket_and_client(self, mock_s3_client):
        """Test initialization with valid bucket and pre-configured client"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        assert service.bucket_name == "test-bucket"
        assert service.s3 == mock_s3_client
        mock_s3_client.head_bucket.assert_called_once_with(Bucket="test-bucket")

    @patch('boto3.client')
    def test_init_creates_client_when_none_provided(self, mock_boto_client, mock_s3_client):
        """Test initialization creates S3 client when none provided"""
        mock_boto_client.return_value = mock_s3_client
        
        service = S3ArtifactService("test-bucket")
        
        assert service.bucket_name == "test-bucket"
        assert service.s3 == mock_s3_client
        mock_boto_client.assert_called_once_with("s3")

    def test_init_with_empty_bucket_name(self):
        """Test initialization with empty bucket name raises ValueError"""
        with pytest.raises(ValueError, match="bucket_name cannot be empty"):
            S3ArtifactService("")

    def test_init_with_none_bucket_name(self):
        """Test initialization with None bucket name raises ValueError"""
        with pytest.raises(ValueError, match="bucket_name cannot be empty"):
            S3ArtifactService(None)

    @patch('boto3.client')
    def test_init_with_no_credentials(self, mock_boto_client):
        """Test initialization with no AWS credentials raises ValueError"""
        mock_boto_client.side_effect = NoCredentialsError()
        
        with pytest.raises(ValueError, match="AWS credentials not found"):
            S3ArtifactService("test-bucket")

    def test_init_bucket_not_found(self, mock_s3_client):
        """Test initialization with non-existent bucket raises ValueError"""
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'HeadBucket'
        )
        
        with pytest.raises(ValueError, match="S3 bucket 'test-bucket' does not exist"):
            S3ArtifactService("test-bucket", s3_client=mock_s3_client)

    def test_init_bucket_access_denied(self, mock_s3_client):
        """Test initialization with access denied to bucket raises ValueError"""
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '403'}}, 'HeadBucket'
        )
        
        with pytest.raises(ValueError, match="Access denied to S3 bucket"):
            S3ArtifactService("test-bucket", s3_client=mock_s3_client)

    def test_init_other_client_error(self, mock_s3_client):
        """Test initialization with other client error raises ValueError"""
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '500'}}, 'HeadBucket'
        )
        
        with pytest.raises(ValueError, match="Failed to access S3 bucket"):
            S3ArtifactService("test-bucket", s3_client=mock_s3_client)


class TestS3ArtifactServiceHelperMethods:
    """Tests for helper methods"""

    def test_file_has_user_namespace_true(self, mock_s3_client):
        """Test _file_has_user_namespace returns True for user: prefix"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        assert service._file_has_user_namespace("user:document.txt")

    def test_file_has_user_namespace_false(self, mock_s3_client):
        """Test _file_has_user_namespace returns False for regular filename"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        assert not service._file_has_user_namespace("document.txt")

    def test_get_object_key_regular_file(self, mock_s3_client):
        """Test _get_object_key for regular files"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        result = service._get_object_key("app", "user1", "session1", "test.txt", 5)
        expected = "app/user1/session1/test.txt/5"
        assert result == expected

    def test_get_object_key_user_namespace(self, mock_s3_client):
        """Test _get_object_key for user namespace files"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        result = service._get_object_key("app", "user1", "session1", "user:test.txt", 3)
        expected = "app/user1/user/test.txt/3"
        assert result == expected

    def test_get_object_key_strips_app_slashes(self, mock_s3_client):
        """Test _get_object_key strips leading/trailing slashes from app_name"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        result = service._get_object_key("/app/", "user1", "session1", "test.txt", 1)
        expected = "app/user1/session1/test.txt/1"
        assert result == expected

    def test_normalize_filename_unicode(self, mock_s3_client):
        """Test _normalize_filename_unicode normalizes Unicode characters"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        # Test with non-breaking space (U+202F)
        filename_with_nbsp = "test\u202ffile.txt"
        normalized = service._normalize_filename_unicode(filename_with_nbsp)
        expected = unicodedata.normalize("NFKC", filename_with_nbsp)
        assert normalized == expected

    def test_normalize_filename_unicode_regular_string(self, mock_s3_client):
        """Test _normalize_filename_unicode with regular ASCII string"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        filename = "regular_file.txt"
        normalized = service._normalize_filename_unicode(filename)
        assert normalized == filename


class TestS3ArtifactServiceSaveArtifact:
    """Tests for save_artifact method"""

    @pytest.mark.asyncio
    async def test_save_artifact_success(self, mock_s3_client, sample_artifact):
        """Test successful artifact saving"""
        # Mock list_versions to return empty list (first version)
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        with patch.object(service, 'list_versions', return_value=[]):
            version = await service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=sample_artifact
            )
        
        assert version == 0
        
        # Verify put_object was called with correct parameters
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]['Bucket'] == 'test-bucket'
        assert call_args[1]['Key'] == 'test_app/user1/session1/test.txt/0'
        assert call_args[1]['Body'] == b"Hello, World!"
        assert call_args[1]['ContentType'] == 'text/plain'
        assert call_args[1]['Metadata']['original_filename'] == 'test.txt'

    @pytest.mark.asyncio
    async def test_save_artifact_increments_version(self, mock_s3_client, sample_artifact):
        """Test that saving multiple artifacts increments version"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock list_versions to return existing versions
        with patch.object(service, 'list_versions', side_effect=[[0], [0, 1]]):
            # Save first artifact (version 1, since 0 exists)
            version1 = await service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=sample_artifact
            )
            
            # Save second artifact (version 2, since 0,1 exist)
            version2 = await service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=sample_artifact
            )
        
        assert version1 == 1
        assert version2 == 2

    @pytest.mark.asyncio
    async def test_save_artifact_user_namespace(self, mock_s3_client, sample_artifact):
        """Test saving artifact with user namespace"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        with patch.object(service, 'list_versions', return_value=[]):
            version = await service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="user:document.txt",
                artifact=sample_artifact
            )
        
        assert version == 0
        
        # Verify correct S3 key structure for user namespace
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]['Key'] == 'test_app/user1/user/document.txt/0'

    @pytest.mark.asyncio
    @pytest.mark.parametrize("artifact_mock", [
        Mock(inline_data=None),
        Mock(inline_data=Mock(data=None))
    ])
    async def test_save_artifact_no_data(self, mock_s3_client, artifact_mock):
        """Test saving artifact with no data raises ValueError"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        with pytest.raises(ValueError, match="Artifact Part has no inline_data to save"):
            await service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=artifact_mock
            )

    @pytest.mark.asyncio
    async def test_save_artifact_client_error(self, mock_s3_client, sample_artifact):
        """Test saving artifact with S3 client error"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        mock_s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': '403', 'Message': 'Access Denied'}}, 'PutObject'
        )
        
        with patch.object(service, 'list_versions', return_value=[]):
            with pytest.raises(OSError, match="Failed to save artifact version"):
                await service.save_artifact(
                    app_name="test_app",
                    user_id="user1",
                    session_id="session1",
                    filename="test.txt",
                    artifact=sample_artifact
                )

    @pytest.mark.asyncio
    async def test_save_artifact_botocore_error(self, mock_s3_client, sample_artifact):
        """Test saving artifact with BotoCore error"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        mock_s3_client.put_object.side_effect = BotoCoreError()
        
        with patch.object(service, 'list_versions', return_value=[]):
            with pytest.raises(OSError, match="BotoCore error saving artifact"):
                await service.save_artifact(
                    app_name="test_app",
                    user_id="user1",
                    session_id="session1",
                    filename="test.txt",
                    artifact=sample_artifact
                )


class TestS3ArtifactServiceLoadArtifact:
    """Tests for load_artifact method"""

    @pytest.mark.asyncio
    async def test_load_artifact_success(self, mock_s3_client, sample_artifact):
        """Test successful artifact loading"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock get_object response
        mock_body = Mock()
        mock_body.read.return_value = b"Hello, World!"
        mock_s3_client.get_object.return_value = {
            'Body': mock_body,
            'ContentType': 'text/plain'
        }
        
        with patch.object(service, 'list_versions', return_value=[0]):
            loaded_artifact = await service.load_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt"
            )
        
        assert loaded_artifact is not None
        assert loaded_artifact.inline_data.data == b"Hello, World!"
        assert loaded_artifact.inline_data.mime_type == "text/plain"
        
        # Verify get_object was called with correct key
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test_app/user1/session1/test.txt/0'
        )

    @pytest.mark.asyncio
    async def test_load_artifact_specific_version(self, mock_s3_client):
        """Test loading specific artifact version"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock get_object response
        mock_body = Mock()
        mock_body.read.return_value = b"Version 5 data"
        mock_s3_client.get_object.return_value = {
            'Body': mock_body,
            'ContentType': 'text/plain'
        }
        
        loaded_artifact = await service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            version=5
        )
        
        assert loaded_artifact is not None
        assert loaded_artifact.inline_data.data == b"Version 5 data"
        
        # Verify get_object was called with correct version
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test_app/user1/session1/test.txt/5'
        )

    @pytest.mark.asyncio
    async def test_load_artifact_latest_version(self, mock_s3_client):
        """Test loading latest version when version not specified"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock get_object response
        mock_body = Mock()
        mock_body.read.return_value = b"Latest version data"
        mock_s3_client.get_object.return_value = {
            'Body': mock_body,
            'ContentType': 'text/plain'
        }
        
        with patch.object(service, 'list_versions', return_value=[0, 1, 2, 5]):
            loaded_artifact = await service.load_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt"
            )
        
        assert loaded_artifact is not None
        assert loaded_artifact.inline_data.data == b"Latest version data"
        
        # Should load version 5 (highest)
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test_app/user1/session1/test.txt/5'
        )

    @pytest.mark.asyncio
    async def test_load_artifact_not_found(self, mock_s3_client):
        """Test loading non-existent artifact returns None"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey'}}, 'GetObject'
        )
        
        loaded_artifact = await service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="nonexistent.txt",
            version=0
        )
        
        assert loaded_artifact is None

    @pytest.mark.asyncio
    async def test_load_artifact_no_versions_available(self, mock_s3_client):
        """Test loading artifact when no versions exist"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        with patch.object(service, 'list_versions', return_value=[]):
            loaded_artifact = await service.load_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt"
            )
        
        assert loaded_artifact is None

    @pytest.mark.asyncio
    async def test_load_artifact_client_error(self, mock_s3_client):
        """Test loading artifact with S3 client error"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': '403'}}, 'GetObject'
        )
        
        loaded_artifact = await service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            version=0
        )
        
        assert loaded_artifact is None

    @pytest.mark.asyncio
    async def test_load_artifact_botocore_error(self, mock_s3_client):
        """Test loading artifact with BotoCore error"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        mock_s3_client.get_object.side_effect = BotoCoreError()
        
        loaded_artifact = await service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            version=0
        )
        
        assert loaded_artifact is None

    @pytest.mark.asyncio
    async def test_load_artifact_user_namespace(self, mock_s3_client):
        """Test loading artifact with user namespace"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock get_object response
        mock_body = Mock()
        mock_body.read.return_value = b"User document data"
        mock_s3_client.get_object.return_value = {
            'Body': mock_body,
            'ContentType': 'text/plain'
        }
        
        loaded_artifact = await service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:document.txt",
            version=0
        )
        
        assert loaded_artifact is not None
        
        # Verify correct S3 key for user namespace
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test_app/user1/user/document.txt/0'
        )


class TestS3ArtifactServiceListArtifactKeys:
    """Tests for list_artifact_keys method"""

    @pytest.mark.asyncio
    async def test_list_artifact_keys_empty(self, mock_s3_client):
        """Test listing artifact keys when none exist"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock empty paginator responses
        paginator = Mock()
        paginator.paginate.return_value = [{'Contents': []}]
        mock_s3_client.get_paginator.return_value = paginator
        
        keys = await service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert keys == []

    @pytest.mark.asyncio
    async def test_list_artifact_keys_session_artifacts(self, mock_s3_client):
        """Test listing session-scoped artifact keys"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator responses
        paginator = Mock()
        session_objects = [
            {'Key': 'test_app/user1/session1/doc1.txt/0'},
            {'Key': 'test_app/user1/session1/doc1.txt/1'},
            {'Key': 'test_app/user1/session1/doc2.txt/0'},
        ]
        user_objects = []
        
        paginator.paginate.side_effect = [
            [{'Contents': session_objects}],  # Session objects
            [{'Contents': user_objects}]       # User objects
        ]
        mock_s3_client.get_paginator.return_value = paginator
        
        keys = await service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert sorted(keys) == ["doc1.txt", "doc2.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_user_artifacts(self, mock_s3_client):
        """Test listing user-scoped artifact keys"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator responses
        paginator = Mock()
        session_objects = []
        user_objects = [
            {'Key': 'test_app/user1/user/profile.txt/0'},
            {'Key': 'test_app/user1/user/settings.txt/0'},
        ]
        
        paginator.paginate.side_effect = [
            [{'Contents': session_objects}],  # Session objects
            [{'Contents': user_objects}]       # User objects
        ]
        mock_s3_client.get_paginator.return_value = paginator
        
        keys = await service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert sorted(keys) == ["user:profile.txt", "user:settings.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_mixed(self, mock_s3_client):
        """Test listing mixed session and user artifact keys"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator responses
        paginator = Mock()
        session_objects = [
            {'Key': 'test_app/user1/session1/session_doc.txt/0'},
        ]
        user_objects = [
            {'Key': 'test_app/user1/user/user_doc.txt/0'},
        ]
        
        paginator.paginate.side_effect = [
            [{'Contents': session_objects}],  # Session objects
            [{'Contents': user_objects}]       # User objects
        ]
        mock_s3_client.get_paginator.return_value = paginator
        
        keys = await service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert sorted(keys) == ["session_doc.txt", "user:user_doc.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_client_error(self, mock_s3_client):
        """Test listing artifact keys with S3 client error"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator that raises error
        paginator = Mock()
        paginator.paginate.side_effect = ClientError(
            {'Error': {'Code': '403'}}, 'ListObjectsV2'
        )
        mock_s3_client.get_paginator.return_value = paginator
        
        keys = await service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        # Should return empty list on error
        assert keys == []


class TestS3ArtifactServiceDeleteArtifact:
    """Tests for delete_artifact method"""

    @pytest.mark.asyncio
    async def test_delete_artifact_success(self, mock_s3_client):
        """Test successful artifact deletion"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        with patch.object(service, 'list_versions', return_value=[0, 1, 2]):
            await service.delete_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt"
            )
        
        # Should delete all versions
        assert mock_s3_client.delete_object.call_count == 3
        
        # Verify correct keys were deleted
        expected_calls = [
            {'Bucket': 'test-bucket', 'Key': 'test_app/user1/session1/test.txt/0'},
            {'Bucket': 'test-bucket', 'Key': 'test_app/user1/session1/test.txt/1'},
            {'Bucket': 'test-bucket', 'Key': 'test_app/user1/session1/test.txt/2'},
        ]
        
        actual_calls = [call[1] for call in mock_s3_client.delete_object.call_args_list]
        assert actual_calls == expected_calls

    @pytest.mark.asyncio
    async def test_delete_artifact_no_versions(self, mock_s3_client):
        """Test deleting artifact with no versions"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        with patch.object(service, 'list_versions', return_value=[]):
            await service.delete_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="nonexistent.txt"
            )
        
        # Should not call delete_object
        mock_s3_client.delete_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_artifact_partial_failure(self, mock_s3_client):
        """Test deleting artifact with some delete failures"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock delete_object to fail on second call
        mock_s3_client.delete_object.side_effect = [
            {},  # Success
            ClientError({'Error': {'Code': '403'}}, 'DeleteObject'),  # Failure
            {},  # Success
        ]
        
        with patch.object(service, 'list_versions', return_value=[0, 1, 2]):
            # Should not raise exception, just log warnings
            await service.delete_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt"
            )
        
        # Should attempt to delete all versions
        assert mock_s3_client.delete_object.call_count == 3


class TestS3ArtifactServiceListVersions:
    """Tests for list_versions method"""

    @pytest.mark.asyncio
    async def test_list_versions_empty(self, mock_s3_client):
        """Test listing versions when artifact doesn't exist"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock empty paginator response
        paginator = Mock()
        paginator.paginate.return_value = [{'Contents': []}]
        mock_s3_client.get_paginator.return_value = paginator
        
        versions = await service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="nonexistent.txt"
        )
        
        assert versions == []

    @pytest.mark.asyncio
    async def test_list_versions_single(self, mock_s3_client):
        """Test listing versions with single version"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator response with single version
        paginator = Mock()
        objects = [{'Key': 'test_app/user1/session1/test.txt/0'}]
        paginator.paginate.return_value = [{'Contents': objects}]
        mock_s3_client.get_paginator.return_value = paginator
        
        versions = await service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == [0]

    @pytest.mark.asyncio
    async def test_list_versions_multiple(self, mock_s3_client):
        """Test listing versions with multiple versions"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator response with multiple versions
        paginator = Mock()
        objects = [
            {'Key': 'test_app/user1/session1/test.txt/0'},
            {'Key': 'test_app/user1/session1/test.txt/2'},
            {'Key': 'test_app/user1/session1/test.txt/1'},
            {'Key': 'test_app/user1/session1/test.txt/5'},
        ]
        paginator.paginate.return_value = [{'Contents': objects}]
        mock_s3_client.get_paginator.return_value = paginator
        
        versions = await service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == [0, 1, 2, 5]  # Should be sorted

    @pytest.mark.asyncio
    async def test_list_versions_ignores_non_numeric(self, mock_s3_client):
        """Test that list_versions ignores non-numeric version parts"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator response with mixed numeric and non-numeric versions
        paginator = Mock()
        objects = [
            {'Key': 'test_app/user1/session1/test.txt/0'},
            {'Key': 'test_app/user1/session1/test.txt/metadata'},
            {'Key': 'test_app/user1/session1/test.txt/1'},
            {'Key': 'test_app/user1/session1/test.txt/invalid'},
        ]
        paginator.paginate.return_value = [{'Contents': objects}]
        mock_s3_client.get_paginator.return_value = paginator
        
        versions = await service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == [0, 1]  # Should only include numeric versions

    @pytest.mark.asyncio
    async def test_list_versions_client_error(self, mock_s3_client):
        """Test listing versions with S3 client error"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator that raises error
        paginator = Mock()
        paginator.paginate.side_effect = ClientError(
            {'Error': {'Code': '403'}}, 'ListObjectsV2'
        )
        mock_s3_client.get_paginator.return_value = paginator
        
        versions = await service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == []

    @pytest.mark.asyncio
    async def test_list_versions_user_namespace(self, mock_s3_client):
        """Test listing versions for user namespace artifact"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator response for user namespace
        paginator = Mock()
        objects = [
            {'Key': 'test_app/user1/user/document.txt/0'},
            {'Key': 'test_app/user1/user/document.txt/1'},
        ]
        paginator.paginate.return_value = [{'Contents': objects}]
        mock_s3_client.get_paginator.return_value = paginator
        
        versions = await service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:document.txt"
        )
        
        assert versions == [0, 1]
        
        # Verify correct prefix was used
        paginator.paginate.assert_called_once_with(
            Bucket='test-bucket',
            Prefix='test_app/user1/user/document.txt/'
        )

    @pytest.mark.asyncio
    async def test_list_versions_strips_app_name_slashes(self, mock_s3_client):
        """Test that list_versions strips slashes from app_name"""
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)
        
        # Mock paginator response
        paginator = Mock()
        objects = [{'Key': 'test_app/user1/session1/test.txt/0'}]
        paginator.paginate.return_value = [{'Contents': objects}]
        mock_s3_client.get_paginator.return_value = paginator
        
        versions = await service.list_versions(
            app_name="/test_app/",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == [0]
        
        # Verify prefix doesn't have leading/trailing slashes
        paginator.paginate.assert_called_once_with(
            Bucket='test-bucket',
            Prefix='test_app/user1/session1/test.txt/'
        )