import {cp,mkdir,readFile,rm,writeFile} from "node:fs/promises";
import path from "node:path";
const root=process.cwd(),dist=path.join(root,"dist");await rm(dist,{recursive:true,force:true});await mkdir(dist,{recursive:true});
for(const file of ["index.html","styles.css","data.js","app.js"])await cp(path.join(root,file),path.join(dist,file));
const[html,css,data,app]=await Promise.all(["index.html","styles.css","data.js","app.js"].map(f=>readFile(path.join(root,f),"utf8")));
const standalone=html.replace('<link rel="stylesheet" href="styles.css" />',()=>`<style>\n${css}\n</style>`).replace('<script src="data.js"></script><script src="app.js"></script>',()=>`<script>\n${data}\n</script><script>\n${app}\n</script>`);
await writeFile(path.join(dist,"Landed-ARV-Pricing-Intelligence-Standalone.html"),standalone);console.log("Built Landed standalone dashboard");
