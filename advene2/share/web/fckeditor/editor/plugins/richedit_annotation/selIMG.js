var oEditor = window.parent.InnerDialogLoaded() ;
var FCKLang = oEditor.FCKLang ;

// execution au chargement de la page

window.onload = function()
{
	// First of all, translate the dialog box texts.
	oEditor.FCKLanguageManager.TranslatePage( document );
	window.parent.SetAutoSize( true ) ;
	// Activate the "OK" button.
	window.parent.SetOkButton( true ) ;

}

function sel(handler)
{
     var sel = document.forms['frmMain'].schema;
     var sch = sel.options[sel.selectedIndex].value;
     while (document.forms['frmMain'].annotationTypes.options.length >1)
    {
          document.forms['frmMain'].annotationTypes.options[1]=null;
     }
     while (document.forms['frmMain'].annotations.options.length >1)
    {
          document.forms['frmMain'].annotations.options[1]=null;
     }
     if (sch != "")
    {
        var url = '../schemas/' + sch + '/view/_xml_annotationTypes_view';
        loadXML(url, handler);
    }
}

function sel2(handler)
{

     var sel = document.forms['frmMain'].annotationTypes;
     var at = sel.options[sel.selectedIndex].value;
     while (document.forms['frmMain'].annotations.options.length >1)
    {
          document.forms['frmMain'].annotations.options[1]=null;
     }
     if (at != "")
    {
         var url = '../annotationTypes/' + at + '/view/_xml_annotations_view';
         loadXML(url, handler);
    }
}
/*
function sel3(handler)
{
        var sel = document.forms['frmMain'].annotations;
	var a = sel.options[sel.selectedIndex].value;
        var aremplir = document.forms['frmMain'].path_req;
        var req = aremplir.value + a;
        aremplir.value = req;
}
*/
function createSel()
{
        var typesAnnot = xmlDoc.getElementsByTagName('annotationTypes')[0];
        var fils = typesAnnot.childNodes; //les annotationType
if (ie)
{
        for (j=0;j < fils.length;j++) 
       {
	document.forms['frmMain'].annotationTypes.options[j+1] = new Option(fils[j].childNodes[0].firstChild.nodeValue, fils[j].getAttribute('id')); // title, id
       }
}
else
{
        for (j=1;j < fils.length-1;j++) 
       {
	document.forms['frmMain'].annotationTypes.options[j] = new Option(fils[j].childNodes[1].firstChild.nodeValue, fils[j].getAttribute('id')); // title, id
       }
}
}

function createSel2()
{
	var annots = xmlDoc.getElementsByTagName('annotations')[0];
        var fils = annots.childNodes; //les annotation
if (ie)
{
        for (j=0;j < fils.length;j++) 
       {
	document.forms['frmMain'].annotations.options[j+1] = new Option(fils[j].childNodes[1].firstChild.nodeValue + " " + fils[j].childNodes[0].firstChild.nodeValue + " " + fils[j].childNodes[2].firstChild.nodeValue, fils[j].getAttribute('id')); //  (0= contenu 1 = begin 2 = end)
       }
}
else 
{
        for (j=1;j < fils.length-1;j++) 
       {
 	document.forms['frmMain'].annotations.options[j] = new Option(fils[j].childNodes[3].firstChild.nodeValue + " " + fils[j].childNodes[1].firstChild.nodeValue + " " + fils[j].childNodes[5].firstChild.nodeValue, fils[j].getAttribute('id')); //  id (1 = contenu 3 = begin 5 = end)
       }
}
}

function loadXML(url, handler)
{      
        ie=false;
	if (document.implementation && document.implementation.createDocument)
	{
		xmlDoc = document.implementation.createDocument("", "", null);
		xmlDoc.async=false;
		xmlDoc.onload = handler;
	}
	else if (window.ActiveXObject)
	{
		xmlDoc = new ActiveXObject("Microsoft.XMLDOM");
		xmlDoc.async=false;
		xmlDoc.onreadystatechange = function () {
			if (xmlDoc.readyState == 4) handler()
		};
                ie=true;
 	}
	else
	{
		alert('Your browser can\'t handle this script');
		return;
	}
	xmlDoc.load(url);
}


function Ok()
{
var img_tmp = '/data/fckeditor/editor/plugins/adv_ima/image_temp.jpg';
var sel = document.forms['frmMain'].schema;
var sch = sel.options[sel.selectedIndex].value
var sel2 = document.forms['frmMain'].annotationTypes;
var at = sel2.options[sel2.selectedIndex].value;
var sel3 = document.forms['frmMain'].annotations;
var a = sel3.options[sel3.selectedIndex].value;
var req = "";
var sHtml = new String('<span contenteditable="false"><div class="AdveneContent" style="float: left; height: 80px; width: 80px;" > contenu </div></span>');

if (sch=="") {
// pas de schéma choisi
req = "here/schemas";
return false; 
} else if (at=="") {
// pas de type d'annotation choisi, que faire ?
req = "here/schemas/"+sch+"/annotationTypes";
return false;
} else if (a=="") {
// pas d'annotation choisie => boucler sur toutes les annotations du type
req = "here/schemas/"+sch+"/annotationTypes/"+at+"/annotations";
sHtml = '<span contenteditable="false"><div class="AdveneContent"  style="height: 80px; width: 80px;" ttal:repeat="a '+ req +'"><p style="text-align: center;">'
} else {//height: 80px; width: 80px; border: 2px solid #FFCCCC;
// annotation choisie
req = "here/annotations/"+a;
sHtml = '<span contenteditable="false"><div class="AdveneContent" style="height: 80px; width: 80px;" ttal:define="a '+req+'"><p style="text-align:center;">'
}
if  (document.forms['frmMain'].link_img_vlc.checked)
{
        sHtml = sHtml + '<a title="'+document.forms['frmMain'].info_bulle_img.value+'" ttal:attributes="href a/player_url"><img ttal:attributes="src a/snapshot_url;alt a/id" src="'+img_tmp+'" />';
	if  (document.forms['frmMain'].titre.checked)
	{ 
		//affiche le nom 
	sHtml = sHtml + '<br/><strong ttal:content="a/representation">Nom</strong>';
	}
sHtml = sHtml + ' </a>';
} else {
// si pas lien on affiche juste image
sHtml = sHtml + '<img ttal:attributes="src a/snapshot_url;alt a/id" src="'+img_tmp+'" /> ';
	if  (document.forms['frmMain'].titre.checked)
	{
		//affiche le nom 
	sHtml = sHtml + '<br/><strong ttal:content="a/content/parsed/nom">Nom</strong>'
	}
}
//  time code
if  (document.forms['frmMain'].time_code.checked)
{
        sHtml = sHtml + '<br/><span style="font-size: 0.8em\;">(<span ttal:content="a/fragment/formatted/begin">Debut</span> - <span ttal:content="a/fragment/formatted/end">Fin</span>)</span>';
}

// lien vers uneautre vue
if  (document.forms['frmMain'].autre_vue.checked)
{
	sHtml = sHtml + '<br/><em>(<a title="'+document.forms['frmMain'].titre_vue.value+'" ttal:attributes="href string:${../view/'+ document.forms['frmMain'].vue.value + '">' + document.forms['frmMain'].vue.value + '</a>)</em>';
}
sHtml = sHtml + '</p></div></span><br>';

var sfinal = sHtml.replace(/ttal/g, 'tal');
oEditor.FCK.InsertHtml(sfinal);
return true ;
}


//activation des zone de saisie
function activevue(object)
{
	if (object.checked==true)
	{
		document.getElementById("vue").disabled=false;
                document.getElementById("titre_vue").disabled=false;
		document.getElementById("vue").focus();			
	}
	else
	{
		document.getElementById("vue").disabled=true;
                document.getElementById("titre_vue").disabled=true;
	}
}
function linkimg(object)
{
	if (object.checked==true)
	{
 		document.getElementById("info_bulle_img").disabled=false;
		document.getElementById("info_bulle_img").focus();			
	}
	else
	{
		document.getElementById("info_bulle_img").disabled=true;
	}
}



