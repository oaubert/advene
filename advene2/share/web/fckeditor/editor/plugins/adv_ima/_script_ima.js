var oEditor = window.parent.InnerDialogLoaded() ;
var FCKLang = oEditor.FCKLang ;
//  variable qui permet de tester le contenu de Width et Height
var exp = new RegExp("^[0-9]+$");
//  variables pour les images temporaires
var img_tmp = '/data/fckeditor/editor/plugins/adv_ima/image_temp.gif';
var img_tmp2 = '/data/fckeditor/editor/plugins/adv_ima/image_temp.jpg';
//  variable des fichiers image admises
var list_ima = new Array("jpeg","jpg","gif","png");

// fonction pour lancer le Popup
window.onload = function(){
	// First of all, translate the dialog box texts.
	oEditor.FCKLanguageManager.TranslatePage( document );
	window.parent.SetAutoSize( true ) ;
	// Activate the "OK" button.
	window.parent.SetOkButton( true ) ;
}

// fonction pour recuperer les donnes dans les formulaire a l'aide de 
// getElementById
function GetE( elementId )
{
	return document.getElementById( elementId )  ;
}

// fonction pour effectuer le split sur le nom du fichier
function nom_fichier(ima, val){
  var ima2 = new Array();
  if (val==''){
    ima2 = ima.split(/[\\\/]/);
  }else{
    ima2 = ima.split(val);
  }
  return ima2[ima2.length-1];
}

// fonction qui permet d'envoyer le fichier dans le packege
// a l'aide de document.nom_form.submit();
function envoyer_image(){
  if(GetE('datafile').value == ''){
    alert('Please choose an Image');
  } else{
    var ima = GetE('datafile').value;
    var ima2 = nom_fichier(ima,'');
    var nam = GetE('nom_fich').value;
    
    if (GetE('nom_fich').value != ''){
      var ima3 = nom_fichier(ima2,'.');
      ima2 = nam + '.' + ima3;
    }
    
    var act = '/packages/advene/resources/image/' + ima2;
    document.frmMain.action = act;
    document.frmMain.submit();
  }
}

function donner_nom_ini(){
  var trouve = false;
  var ima = GetE('datafile').value;
  var ima2 = nom_fichier(ima,'');
  var nom_ima = ima2.split('.');
  var ext = nom_ima[1].toLowerCase();
  
  for (var i=0; i<list_ima.length; i++){
    if(list_ima[i] == ext){ trouve=true;}
  }
  if(trouve == true){
    GetE('nom_fich').value = nom_ima[0];
  }else{
    alert('Fichier non accepte\'!');
    GetE('datafile').value = '';
    GetE('nom_fich').value = '';
  }
}

// fonction Ok qui permet de creer une balise img dans la textarea de fckeditor
// elle a deux src:
//    1) ttal:attributes="src packages/advene/resources/image/ : permet 
//          de contacter le packege et de trouver l'image
//    2) "/data/fckeditor/editor/plugins/adv_ima/image_temp.gif" : permet 
//          d'afficher une image temporaire
function Ok(){
  var wid = GetE('wid_fich').value;
  var hei = GetE('hei_fich').value;
  var nam = GetE('nom_fich').value;

  if(GetE('datafile').value==""){
    alert('Please choose an Image');
    return false;
  }else{
    var ima = GetE('datafile').value;
    var sHtml = new String('<span contenteditable="false">');
    var ima2,sHtml_final;
    
    if(nam==''){
      ima2 = nom_fichier(ima,'');
    }else{
      ima2 = nom_fichier(ima,'');
      var ima3 = nom_fichier(ima2,'.');
      ima2 = nam + '.' + ima3;
    }
    
    sHtml = sHtml + '<img alt="'+ ima2 + '" ttal:attributes="src package/resources/image/' + ima2; 
    sHtml = sHtml + '/absolute_url" src="' + img_tmp + '" ';
    
    if(hei == '' || wid == ''){
      sHtml = sHtml + '/></span>';
    }else{
      if(exp.test(hei) == false || exp.test(wid) == false){
        alert('Only Number in Width and Heigth');
        return false;
      }else{
        sHtml = sHtml + 'width="' + wid + '" height="' + hei + '" /></span>';
      }
    }
  }
    
  sHtml_final = sHtml.replace(/ttal/g, 'tal');
  oEditor.FCK.InsertHtml(sHtml_final);
  return true ;
}


/* function Ok() pour integrer ajax (supprimer function envoyer_fichier())

function Ok(){
  //file upload
  if(document.frmMain.imgs.value==""){
    alert("Choose an Image!");
    return false;
  }else{
    var ima, ima2, contenu;
    var sHtml = new String('<span contenteditable="false">');
    ima = document.frmMain.imgs.value;
    ima2 = nom_fichier(ima);
	   
	   if(window.XMLHttpRequest) // Firefox 
	    req = new XMLHttpRequest(); 
	   else if(window.ActiveXObject) // Internet Explorer 
	    req = new ActiveXObject("Microsoft.XMLHTTP"); 
     else { // XMLHttpRequest non supporté par le navigateur 
	     alert("Votre navigateur ne supporte pas les objets XMLHTTPRequest..."); 
	   return; 
  	 } 
  
  	req.open('PUT', 'http://localhost:1234/packages/advene/resources/image/'+ima2, false);
  	req.send(ima);
    
    sHtml = sHtml + '<img alt="'+ ima2 + '" ttal:attributes="src packages/advene/resources/image/' + ima2 + '" /></span>';
    oEditor.FCK.InsertHtml(sHtml);
    return true ;
  }
}
*/