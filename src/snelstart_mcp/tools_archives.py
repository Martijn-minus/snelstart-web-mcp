from mcp.types import ToolAnnotations

from .backup import create_archive, list_archives, unpack_archive, verify_archive
from .client import Client
from .config import SnelStartError
from .models.requests import ArchiveCreateRequest, ArchiveRequest
from .models.responses import (
    ArchiveListEntry,
    CreatedArchiveResponse,
    DataResponse,
    ExtractedArchiveResponse,
    VerifiedArchiveResponse,
)
from .tooling import Register


def register_archive_tools(tool: Register, client: Client) -> None:
    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    def snelstart_create_year_archive(request: ArchiveCreateRequest) -> CreatedArchiveResponse:
        """Make a private local year archive. It can include the official SnelStart ZIP or a BACPAC."""
        return CreatedArchiveResponse.model_validate(
            create_archive(
                client.store,
                request.year,
                request.through_date,
                client=client if request.live_export else None,
                audit_file=request.auditfile_path,
                attachments=request.attachments_zip_path,
                administration_backup=request.bacpac_path,
                official_export=request.official_zip_path,
            )
        )

    @tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_verify_archive(request: ArchiveRequest) -> VerifiedArchiveResponse:
        """Verify every file size and SHA-256 in a local archive."""
        return VerifiedArchiveResponse.model_validate(verify_archive(client.store, request.archive))

    @tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_list_archives() -> DataResponse[list[ArchiveListEntry]]:
        """List local year backups with their creation date and scope. Use the verify tool to check file checksums."""
        inventory = list_archives(client.store)
        if inventory.error:
            raise SnelStartError(inventory.error)
        return DataResponse(data=inventory.archives)

    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_extract_archive(request: ArchiveRequest) -> ExtractedArchiveResponse:
        """Verify and extract an archive to a new private local folder."""
        return ExtractedArchiveResponse.model_validate(
            unpack_archive(client.store, request.archive)
        )
