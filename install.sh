#!/bin/sh -e

OS=$(uname -s)
ARCH=$(uname -m)
TARGET=
CHANNEL="${XENAGE_CHANNEL:-}"

if [ "${OS}" = "Linux" ]
then
    if [ "${ARCH}" = "x86_64" ] || [ "${ARCH}" = "amd64" ] || [ "${ARCH}" = "x64" ]
    then
        TARGET="linux-x86_64"
    elif [ "${ARCH}" = "aarch64" ] || [ "${ARCH}" = "arm64" ] || [ "${ARCH}" = "arm64e" ]
    then
        TARGET="linux-aarch64"
    fi
elif [ "${OS}" = "Darwin" ]
then
    if [ "${ARCH}" = "x86_64" ] || [ "${ARCH}" = "amd64" ] || [ "${ARCH}" = "x64" ]
    then
        TARGET="darwin-x86_64"
    elif [ "${ARCH}" = "aarch64" ] || [ "${ARCH}" = "arm64" ] || [ "${ARCH}" = "arm64e" ]
    then
        TARGET="darwin-aarch64"
    fi
elif [ "${OS}" = "MINGW64_NT" ] || [ "${OS}" = "MINGW32_NT" ] || [ "${OS}" = "MSYS_NT" ] || [ "${OS}" = "CYGWIN_NT" ]
then
    if [ "${ARCH}" = "x86_64" ] || [ "${ARCH}" = "amd64" ] || [ "${ARCH}" = "x64" ]
    then
        TARGET="windows-x86_64"
    elif [ "${ARCH}" = "aarch64" ] || [ "${ARCH}" = "arm64" ] || [ "${ARCH}" = "arm64e" ]
    then
        TARGET="windows-aarch64"
    fi
fi

if [ -z "${TARGET}" ]
then
    echo "Operating system '${OS}' / architecture '${ARCH}' is unsupported."
    exit 1
fi

if [ -z "${CHANNEL}" ]
then
    if [ -r /dev/tty ]
    then
        echo
        echo "Choose release channel:"
        echo "  1) Latest"
        echo "  2) Development"
        echo -n "Select [1/2] (default 2): "
        read answer < /dev/tty || true
        if [ "${answer}" = "1" ] || [ "${answer}" = "latest" ] || [ "${answer}" = "Latest" ]
        then
            CHANNEL="latest"
        else
            CHANNEL="development"
        fi
    else
        CHANNEL="development"
    fi
fi

if [ "${CHANNEL}" != "latest" ] && [ "${CHANNEL}" != "development" ]
then
    echo "Unsupported channel '${CHANNEL}'. Use latest or development."
    exit 1
fi

BASE_URL="${XENAGE_INSTALL_BASE_URL:-https://xenage.dev}"
URL="${BASE_URL%/}/api/install/xenage?target=${TARGET}&channel=${CHANNEL}"

xenage_download_filename_prefix="xenage"
xenage="$xenage_download_filename_prefix"
if [ "${TARGET#windows-}" != "${TARGET}" ]
then
    xenage="${xenage}.exe"
fi

if [ -f "$xenage" ]
then
    echo -n "Xenage binary ${xenage} already exists. Overwrite? [y/N] "
    read answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]
    then
        rm -f "$xenage"
    else
        i=0
        while [ -f "$xenage" ]
        do
            xenage="${xenage_download_filename_prefix}.${i}"
            if [ "${TARGET#windows-}" != "${TARGET}" ]
            then
                xenage="${xenage}.exe"
            fi
            i=$((i+1))
        done
    fi
fi

echo
echo "Will download ${URL} into ${xenage}"
echo
tmp_download="${xenage}.download.tmp"
http_code=$(curl -sSL -w "%{http_code}" -o "${tmp_download}" "${URL}")
if [ "${http_code}" != "200" ]
then
    echo "Backend download failed with HTTP ${http_code}"
    cat "${tmp_download}"
    rm -f "${tmp_download}"
    exit 1
fi

mv "${tmp_download}" "${xenage}"
chmod a+x "${xenage}" || exit 1

echo
echo "Successfully downloaded Xenage binary (${CHANNEL}), you can run it as:"
echo "    ./${xenage} init"
