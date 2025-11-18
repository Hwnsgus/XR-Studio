import unreal
for a in unreal.EditorAssetLibrary.list_assets('/Game/Scripts/ExportedFBX', True):
    d = unreal.EditorAssetLibrary.find_asset_data(a)
    unreal.log(f"{d.asset_class} {a}")
