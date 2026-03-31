# LibreOffice Third-Party License Notice

## About LibreOffice

LibreOffice is a free and open-source office productivity software suite developed by The Document Foundation. When the SAM Docker image is built with `INSTALL_LIBREOFFICE=true`, the unmodified LibreOffice packages from Debian are installed as a **separate application** alongside SAM to provide document conversion capabilities (DOCX, PPTX, XLSX to PDF).

**Important:** LibreOffice is NOT bundled by default. It is only installed when explicitly requested via the `INSTALL_LIBREOFFICE=true` build argument.

## License

LibreOffice is licensed under the **Mozilla Public License Version 2.0 (MPL-2.0)**.

Some components may also be available under the GNU Lesser General Public License (LGPL).

### Mozilla Public License Version 2.0

The full text of the MPL-2.0 license can be found at:
- https://www.mozilla.org/en-US/MPL/2.0/

### LGPL License

The full text of the LGPL can be found at:
- https://www.gnu.org/licenses/lgpl-3.0.html

## Source Code

LibreOffice source code is available from:
- **Official website:** https://www.libreoffice.org/download/source-code/
- **Git repository:** https://git.libreoffice.org/core
- **Debian source packages:** Available via `apt-get source libreoffice-writer-nogui` (when using Debian-based images)

## How LibreOffice is Used

SAM uses LibreOffice in **headless mode** via command-line interface to convert Office documents (DOCX, PPTX, XLSX) to PDF format for in-browser preview. The conversion is performed by calling the `soffice` binary with the `--headless --convert-to pdf` flags.

No modifications have been made to LibreOffice's source code. The standard Debian packages are installed as-is:
- `libreoffice-writer-nogui`
- `libreoffice-impress-nogui`
- `libreoffice-calc-nogui`

## Additional Information

- **LibreOffice Official Website:** https://www.libreoffice.org/
- **The Document Foundation:** https://www.documentfoundation.org/
- **LibreOffice License FAQ:** https://www.libreoffice.org/about-us/licenses/

---

*This notice is provided in compliance with LibreOffice's licensing requirements. LibreOffice is a trademark of The Document Foundation.*
