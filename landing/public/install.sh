#!/bin/sh -e

OS=$(uname -s)
ARCH=$(uname -m)
TARGET=
CHANNEL_RAW="${XENAGE_CHANNEL:-}"
CHANNEL=
ALLOW_CHANNEL_CHOICE=0

for arg in "$@"
do
    case "${arg}" in
        --choose|--chose)
            ALLOW_CHANNEL_CHOICE=1
            ;;
        *)
            echo "Unknown argument: ${arg}"
            echo "Usage: sh install.sh [--choose]"
            exit 1
            ;;
    esac
done

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

if [ -n "${CHANNEL_RAW}" ]
then
    case "${CHANNEL_RAW}" in
        latest|main|nightly)
            CHANNEL="latest"
            ;;
        development|dev)
            CHANNEL="development"
            ;;
        *)
            echo "Unsupported channel '${CHANNEL_RAW}'. Use latest/main/nightly or development/dev."
            exit 1
            ;;
    esac
fi

if [ -z "${CHANNEL}" ]
then
    if [ "${ALLOW_CHANNEL_CHOICE}" = "1" ] && [ -r /dev/tty ]
    then
        echo
        echo "Choose release channel:"
        echo "  1) Main (nightly latest.json)"
        echo "  2) Development"
        printf "Select [1/2] (default 1): "
        read answer < /dev/tty || true
        if [ -z "${answer}" ] || [ "${answer}" = "1" ] || [ "${answer}" = "latest" ] || [ "${answer}" = "Latest" ] || [ "${answer}" = "main" ] || [ "${answer}" = "nightly" ]
        then
            CHANNEL="latest"
        else
            CHANNEL="development"
        fi
    else
        CHANNEL="latest"
    fi
fi

if [ "${CHANNEL}" != "latest" ] && [ "${CHANNEL}" != "development" ]
then
    echo "Unsupported channel '${CHANNEL}'. Use latest/main/nightly or development/dev."
    exit 1
fi

BASE_URL="${XENAGE_INSTALL_BASE_URL:-https://xenage.dev}"
URL="${BASE_URL%/}/api/install/xenage?target=${TARGET}&channel=${CHANNEL}&manifest=latest_cli"

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
