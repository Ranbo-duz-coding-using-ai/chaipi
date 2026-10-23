import bpy, bmesh, sys, os, glob
d = sys.argv[sys.argv.index('--') + 1]
for f in sorted(glob.glob(os.path.join(d, '*.stl'))):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try: bpy.ops.wm.stl_import(filepath=f)
    except AttributeError: bpy.ops.import_mesh.stl(filepath=f)
    ob = bpy.context.selected_objects[0]; bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    nm = [e for e in bm.edges if not e.is_manifold]; dims = ob.dimensions
    print('CHECK', os.path.basename(f), 'tris', len(bm.faces), 'non-manifold edges', len(nm), 'size mm %.2f x %.2f x %.2f' % (dims.x, dims.y, dims.z))
    bm.free()
