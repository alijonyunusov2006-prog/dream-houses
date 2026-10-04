@echo off
rem Qabat: download 12 logo options (SVG) into Downloads\Qabat-logos
set "DIR=%USERPROFILE%\Downloads\Qabat-logos"
if not exist "%DIR%" mkdir "%DIR%"
echo Downloading Qabat logos to %DIR% ...
curl -L -s -f -o "%DIR%\01-soplo-sloi.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125216_bbd82693-adea-4f84-bac1-d9243a3a2901.svg" && echo   ok  01-soplo-sloi || echo   FAILED  01-soplo-sloi
curl -L -s -f -o "%DIR%\02-soplo-Q-nit.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125217_98c5d89b-7454-43d4-b7df-0727f2fc3798.svg" && echo   ok  02-soplo-Q-nit || echo   FAILED  02-soplo-Q-nit
curl -L -s -f -o "%DIR%\03-nastolnaya-lampa.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125216_7e326841-e00d-4a05-9021-be1bc174f03f.svg" && echo   ok  03-nastolnaya-lampa || echo   FAILED  03-nastolnaya-lampa
curl -L -s -f -o "%DIR%\04-sloi-stupenkoy.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125217_39a978c5-5158-4ea6-9d6e-aa59b65559ba.svg" && echo   ok  04-sloi-stupenkoy || echo   FAILED  04-sloi-stupenkoy
curl -L -s -f -o "%DIR%\05-Q-odnoy-liniey.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125216_5cc33910-5b3c-49cb-841e-7bfa860b4720.svg" && echo   ok  05-Q-odnoy-liniey || echo   FAILED  05-Q-odnoy-liniey
curl -L -s -f -o "%DIR%\06-domik-iz-sloev.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125216_f06e9c60-0da3-4d61-b70b-265bf57d7640.svg" && echo   ok  06-domik-iz-sloev || echo   FAILED  06-domik-iz-sloev
curl -L -s -f -o "%DIR%\07-Q-sloyami.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125216_98ca510b-64ce-4cb5-b06f-82e6d38f9a6e.svg" && echo   ok  07-Q-sloyami || echo   FAILED  07-Q-sloyami
curl -L -s -f -o "%DIR%\08-kubik-v-pechati.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125217_3cfa471b-cc59-458e-af74-4d11edbc705a.svg" && echo   ok  08-kubik-v-pechati || echo   FAILED  08-kubik-v-pechati
curl -L -s -f -o "%DIR%\09-podvesnaya-lampa.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125217_e115b401-e167-4b7a-8e3f-15bac5b0cf1c.svg" && echo   ok  09-podvesnaya-lampa || echo   FAILED  09-podvesnaya-lampa
curl -L -s -f -o "%DIR%\10-krugly-znachok.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125216_91547ac4-6579-4341-9763-56b56f6e02d6.svg" && echo   ok  10-krugly-znachok || echo   FAILED  10-krugly-znachok
curl -L -s -f -o "%DIR%\11-vaza-spiral.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125217_ccc91f36-ad31-42ab-a92c-f849bf266df1.svg" && echo   ok  11-vaza-spiral || echo   FAILED  11-vaza-spiral
curl -L -s -f -o "%DIR%\12-Q-hvost-soplo.svg" "https://d8j0ntlcm91z4.cloudfront.net/user_3ElkwKvj3PbkMSEZvzI8hrexIy2/hf_20261004_125218_7c325987-c7cf-4112-a697-bbcffd53645c.svg" && echo   ok  12-Q-hvost-soplo || echo   FAILED  12-Q-hvost-soplo
echo.
echo Done. Opening the folder...
explorer "%DIR%"
timeout /t 5 >nul
